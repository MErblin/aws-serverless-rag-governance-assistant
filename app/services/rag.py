"""
DocuChat RAG - RAG Query Service

Handles retrieval and generation using LlamaIndex with per-project isolation.
Includes lightweight hybrid retrieval + query routing + heuristic reranking.
"""

from __future__ import annotations

import math
import re
import logging
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from llama_index.core import StorageContext, VectorStoreIndex, load_index_from_storage
from llama_index.core import Settings as LlamaSettings
from llama_index.core.schema import NodeWithScore
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.llms.ollama import Ollama

from app.config import get_settings
from app.services.projects import ProjectStore

settings = get_settings()
logger = logging.getLogger("docuchat.api.rag")


class RAGService:
    """Service for RAG-based document querying."""

    def __init__(self) -> None:
        self.project_store = ProjectStore()
        self.project_store.ensure_default_project()

        LlamaSettings.llm = Ollama(
            model=settings.ollama_model,
            base_url=settings.ollama_base_url,
            request_timeout=120.0,
        )
        LlamaSettings.embed_model = HuggingFaceEmbedding(model_name=settings.embedding_model)

    def _load_index(self, index_dir: Path) -> VectorStoreIndex:
        try:
            if (index_dir / "docstore.json").exists():
                storage_context = StorageContext.from_defaults(persist_dir=str(index_dir))
                return load_index_from_storage(storage_context)
            return VectorStoreIndex([])
        except Exception:
            logger.exception("Error loading project index")
            return VectorStoreIndex([])

    def _tokenize(self, text: str) -> list[str]:
        return re.findall(r"[a-zA-Z0-9_]+", text.lower())

    def _route_query(self, question: str) -> str:
        """Lightweight query router for retrieval strategy tuning."""
        q = question.lower()
        if any(k in q for k in ["exact", "clause", "policy", "contract", "invoice", "billing", "section"]):
            return "lexical_heavy"
        if any(k in q for k in ["summary", "summarize", "overview", "main points"]):
            return "dense_heavy"
        return "balanced"

    def _dense_retrieve(self, index: VectorStoreIndex, question: str, top_k: int) -> list[NodeWithScore]:
        retriever = index.as_retriever(similarity_top_k=top_k)
        nodes = retriever.retrieve(question)
        return list(nodes or [])

    def _bm25_like_retrieve(
        self,
        index: VectorStoreIndex,
        question: str,
        top_k: int,
    ) -> list[NodeWithScore]:
        query_tokens = self._tokenize(question)
        if not query_tokens:
            return []

        all_docs = getattr(index.docstore, "docs", {}) or {}
        if not all_docs:
            return []

        node_tokens: dict[str, list[str]] = {}
        doc_freq: dict[str, int] = defaultdict(int)
        avg_doc_len = 0.0

        for node_id, node in all_docs.items():
            text = getattr(node, "text", "") or ""
            tokens = self._tokenize(text)
            if not tokens:
                continue
            node_tokens[node_id] = tokens
            avg_doc_len += len(tokens)
            for term in set(tokens):
                doc_freq[term] += 1

        if not node_tokens:
            return []

        n_docs = len(node_tokens)
        avg_doc_len = avg_doc_len / max(1, n_docs)
        k1 = 1.5
        b = 0.75

        scored: list[tuple[str, float]] = []
        for node_id, tokens in node_tokens.items():
            tf = Counter(tokens)
            doc_len = len(tokens)
            score = 0.0

            for term in query_tokens:
                if term not in tf:
                    continue
                df = doc_freq.get(term, 0)
                if df == 0:
                    continue

                idf = math.log(1 + ((n_docs - df + 0.5) / (df + 0.5)))
                term_tf = tf[term]
                denom = term_tf + k1 * (1 - b + b * (doc_len / max(avg_doc_len, 1e-9)))
                score += idf * ((term_tf * (k1 + 1)) / max(denom, 1e-9))

            if score > 0:
                scored.append((node_id, score))

        scored.sort(key=lambda x: x[1], reverse=True)
        top = scored[:top_k]

        results: list[NodeWithScore] = []
        for node_id, score in top:
            node = all_docs.get(node_id)
            if node is not None:
                results.append(NodeWithScore(node=node, score=float(score)))
        return results

    def _reciprocal_rank_fusion(
        self,
        dense_nodes: list[NodeWithScore],
        lexical_nodes: list[NodeWithScore],
        top_k: int,
        route_mode: str,
    ) -> list[NodeWithScore]:
        rrf_k = 60
        fused_scores: dict[str, float] = defaultdict(float)
        node_map: dict[str, NodeWithScore] = {}

        dense_weight = 1.0
        lexical_weight = 1.0
        if route_mode == "lexical_heavy":
            lexical_weight = 1.35
            dense_weight = 0.85
        elif route_mode == "dense_heavy":
            dense_weight = 1.35
            lexical_weight = 0.85

        for rank, item in enumerate(dense_nodes, start=1):
            node_id = item.node.node_id
            fused_scores[node_id] += dense_weight * (1.0 / (rrf_k + rank))
            node_map[node_id] = item

        for rank, item in enumerate(lexical_nodes, start=1):
            node_id = item.node.node_id
            fused_scores[node_id] += lexical_weight * (1.0 / (rrf_k + rank))
            if node_id not in node_map:
                node_map[node_id] = item

        ranked_ids = sorted(fused_scores.keys(), key=lambda nid: fused_scores[nid], reverse=True)
        output: list[NodeWithScore] = []
        for node_id in ranked_ids[:top_k]:
            base = node_map[node_id]
            output.append(NodeWithScore(node=base.node, score=float(fused_scores[node_id])))
        return output

    def _heuristic_rerank(self, question: str, nodes: list[NodeWithScore], top_k: int) -> list[NodeWithScore]:
        """CPU-cheap rerank using token overlap + position bonus."""
        q_tokens = set(self._tokenize(question))
        if not q_tokens:
            return nodes[:top_k]

        rescored: list[NodeWithScore] = []
        for idx, item in enumerate(nodes):
            text = (getattr(item.node, "text", "") or "")[:1200]
            t_tokens = set(self._tokenize(text))
            overlap = len(q_tokens & t_tokens) / max(1, len(q_tokens))
            base = float(item.score or 0.0)
            position_bonus = 1.0 / (idx + 1)
            combined = (0.55 * base) + (0.35 * overlap) + (0.10 * position_bonus)
            rescored.append(NodeWithScore(node=item.node, score=combined))

        rescored.sort(key=lambda n: float(n.score or 0.0), reverse=True)
        return rescored[:top_k]

    async def query(
        self,
        question: str,
        project_id: str,
        include_diagnostics: bool = False,
    ) -> tuple[str, list[dict], float, bool, dict[str, Any] | None]:
        project = self.project_store.get_project(project_id)
        if not project:
            raise ValueError(f"Project not found: {project_id}")

        model = project.get("model") or settings.ollama_model
        LlamaSettings.llm = Ollama(
            model=model,
            base_url=settings.ollama_base_url,
            request_timeout=120.0,
        )

        paths = self.project_store.get_project_paths(project_id)
        index = self._load_index(paths["index_dir"])

        top_k = int(project.get("top_k", 3) or 3)
        system_prompt = project.get("system_prompt") or settings.default_system_prompt
        route_mode = self._route_query(question)

        candidate_k = max(top_k * 4, top_k)
        dense_nodes = self._dense_retrieve(index, question, candidate_k)
        lexical_nodes = self._bm25_like_retrieve(index, question, candidate_k)
        fused_nodes = self._reciprocal_rank_fusion(dense_nodes, lexical_nodes, top_k=candidate_k, route_mode=route_mode)
        reranked_nodes = self._heuristic_rerank(question, fused_nodes, top_k=top_k)

        if not reranked_nodes:
            answer = "I don't have enough grounded context in this project's documents to answer confidently."
            return answer, [], 0.0, True, {
                "retrieval_mode": "hybrid_rrf_rerank",
                "route_mode": route_mode,
                "dense_count": len(dense_nodes),
                "lexical_count": len(lexical_nodes),
                "fused_count": 0,
            } if include_diagnostics else None

        context_blocks = []
        citations: list[dict] = []
        score_values: list[float] = []

        for item in reranked_nodes:
            node = item.node
            score = float(item.score) if item.score is not None else 0.0
            score = max(0.0, min(1.0, score))
            score_values.append(score)

            filename = node.metadata.get("filename", "unknown")
            chunk_id = getattr(node, "node_id", "unknown")
            text = getattr(node, "text", "") or ""

            context_blocks.append(f"[source: {filename} | chunk: {chunk_id}]\n{text}")
            citations.append(
                {
                    "filename": filename,
                    "chunk_id": chunk_id,
                    "score": round(score, 4),
                }
            )

        confidence = round(sum(score_values) / len(score_values), 4) if score_values else 0.0
        abstained = confidence < 0.06

        if abstained:
            answer = "I don't have enough grounded context in this project's documents to answer confidently."
        else:
            joined_context = "\n\n".join(context_blocks)
            prompt = (
                f"{system_prompt}\n\n"
                "Use only the provided context. If uncertain, say you don't know.\n\n"
                f"Context:\n{joined_context}\n\n"
                f"Question: {question}\n"
                "Answer:"
            )
            llm_response = LlamaSettings.llm.complete(prompt)
            answer = str(getattr(llm_response, "text", llm_response))

        diagnostics = None
        if include_diagnostics:
            diagnostics = {
                "retrieval_mode": "hybrid_rrf_rerank",
                "route_mode": route_mode,
                "dense_count": len(dense_nodes),
                "lexical_count": len(lexical_nodes),
                "fused_count": len(fused_nodes),
                "reranked_count": len(reranked_nodes),
                "top_k": top_k,
            }

        return answer, citations, confidence, abstained, diagnostics

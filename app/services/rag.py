"""
DocuChat RAG - RAG Query Service

Handles retrieval and generation using LlamaIndex with per-project isolation.
"""

from __future__ import annotations

from pathlib import Path

from llama_index.core import StorageContext, VectorStoreIndex, load_index_from_storage
from llama_index.core import Settings as LlamaSettings
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.llms.ollama import Ollama

from app.config import get_settings
from app.services.projects import ProjectStore

settings = get_settings()


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
        except Exception as e:
            print(f"Error loading index in RAG Service: {e}")
            return VectorStoreIndex([])

    async def query(self, question: str, project_id: str) -> tuple[str, list[dict], float, bool]:
        """
        Query documents and generate an answer.

        Returns:
            (answer, citations, confidence, abstained)
        """
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

        query_engine = index.as_query_engine(
            streaming=False,
            similarity_top_k=top_k,
            text_qa_template=None,
        )

        full_question = f"{system_prompt}\n\nUser question: {question}"
        response = query_engine.query(full_question)

        citations: list[dict] = []
        score_values: list[float] = []

        if response.source_nodes:
            for node in response.source_nodes:
                score = float(node.score) if node.score is not None else 0.0
                score_values.append(max(0.0, min(1.0, score)))
                chunk_id = getattr(getattr(node, "node", None), "node_id", None) or getattr(node, "node_id", "unknown")
                citations.append(
                    {
                        "filename": node.metadata.get("filename", "unknown"),
                        "chunk_id": chunk_id,
                        "score": round(score, 4),
                    }
                )

        confidence = round(sum(score_values) / len(score_values), 4) if score_values else 0.0
        abstained = confidence < 0.2

        if abstained:
            answer = "I don't have enough grounded context in this project's documents to answer confidently."
        else:
            answer = str(response)

        return answer, citations, confidence, abstained

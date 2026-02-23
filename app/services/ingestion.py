"""
DocuChat RAG - Document Ingestion Service

Handles document loading, parsing, and per-project vector indexing.
"""

from __future__ import annotations

from pathlib import Path
import shutil
import logging

import fitz  # PyMuPDF
from llama_index.core import Document, StorageContext, VectorStoreIndex, load_index_from_storage
from llama_index.core import Settings as LlamaSettings
from llama_index.embeddings.huggingface import HuggingFaceEmbedding

from app.config import get_settings
from app.services.projects import ProjectStore

settings = get_settings()
logger = logging.getLogger("docuchat.api.ingestion")


class IngestionService:
    """Service for processing and indexing documents."""

    def __init__(self) -> None:
        self.project_store = ProjectStore()
        self.project_store.ensure_default_project()

        # Configure LlamaIndex to use local embedding model
        LlamaSettings.embed_model = HuggingFaceEmbedding(model_name=settings.embedding_model)

    def _load_or_create_index(self, index_dir: Path) -> VectorStoreIndex:
        index_dir.mkdir(parents=True, exist_ok=True)
        try:
            if (index_dir / "docstore.json").exists():
                storage_context = StorageContext.from_defaults(persist_dir=str(index_dir))
                return load_index_from_storage(storage_context)
            return VectorStoreIndex([])
        except Exception:
            logger.exception("Error loading index, creating new one")
            return VectorStoreIndex([])

    async def process_document(self, file_content: bytes, filename: str, project_id: str) -> str:
        """Process and index a document into a specific project."""
        filename = Path(filename).name
        project = self.project_store.get_project(project_id)
        if not project:
            raise ValueError(f"Project not found: {project_id}")

        paths = self.project_store.get_project_paths(project_id)
        index_dir = paths["index_dir"]
        documents_dir = paths["documents_dir"]
        documents_dir.mkdir(parents=True, exist_ok=True)

        file_ext = filename.split(".")[-1].lower()
        if file_ext == "pdf":
            text = self._extract_text_from_pdf(file_content)
        elif file_ext == "txt":
            text = self._extract_text_from_txt(file_content)
        else:
            raise ValueError(f"Unsupported file type: {file_ext}")

        index = self._load_or_create_index(index_dir)

        doc = Document(
            text=text,
            metadata={
                "filename": filename,
                "file_type": file_ext,
                "project_id": project_id,
            },
        )
        index.insert(doc)
        index.storage_context.persist(persist_dir=str(index_dir))

        # Keep original file for auditing/demo traceability
        (documents_dir / filename).write_bytes(file_content)
        logger.info("Document indexed", extra={"project_id": project_id, "filename": filename})

        return doc.doc_id

    def _extract_text_from_pdf(self, file_content: bytes) -> str:
        with fitz.open(stream=file_content, filetype="pdf") as doc:
            text = ""
            for page in doc:
                text += page.get_text()
        return text

    async def rebuild_project_index(self, project_id: str) -> dict:
        """Rebuild the full index for a project from files on disk."""
        project = self.project_store.get_project(project_id)
        if not project:
            raise ValueError(f"Project not found: {project_id}")

        paths = self.project_store.get_project_paths(project_id)
        index_dir = paths["index_dir"]
        docs_dir = paths["documents_dir"]
        docs_dir.mkdir(parents=True, exist_ok=True)

        if index_dir.exists():
            shutil.rmtree(index_dir, ignore_errors=True)
        index_dir.mkdir(parents=True, exist_ok=True)

        index = VectorStoreIndex([])
        indexed_count = 0

        for p in sorted(docs_dir.iterdir()):
            if not p.is_file():
                continue
            ext = p.suffix.lower().lstrip(".")
            if ext not in {"pdf", "txt"}:
                continue

            content = p.read_bytes()
            if ext == "pdf":
                text = self._extract_text_from_pdf(content)
            else:
                text = self._extract_text_from_txt(content)

            doc = Document(
                text=text,
                metadata={
                    "filename": p.name,
                    "file_type": ext,
                    "project_id": project_id,
                },
            )
            index.insert(doc)
            indexed_count += 1

        index.storage_context.persist(persist_dir=str(index_dir))
        return {"project_id": project_id, "indexed_documents": indexed_count}

    async def delete_document(self, project_id: str, filename: str) -> dict:
        """Delete a project document and rebuild index to keep storage consistent."""
        project = self.project_store.get_project(project_id)
        if not project:
            raise ValueError(f"Project not found: {project_id}")

        docs_dir = self.project_store.get_project_paths(project_id)["documents_dir"]
        target = docs_dir / filename
        if not target.exists() or not target.is_file():
            raise ValueError(f"Document not found: {filename}")

        target.unlink()
        rebuild = await self.rebuild_project_index(project_id)
        return {"deleted": filename, **rebuild}

    def _extract_text_from_txt(self, file_content: bytes) -> str:
        return file_content.decode("utf-8", errors="ignore")

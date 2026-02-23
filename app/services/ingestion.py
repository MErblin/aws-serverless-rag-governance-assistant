"""
DocuChat RAG - Document Ingestion Service

Handles document loading, parsing, and per-project vector indexing.
"""

from __future__ import annotations

from pathlib import Path

import fitz  # PyMuPDF
from llama_index.core import Document, StorageContext, VectorStoreIndex, load_index_from_storage
from llama_index.core import Settings as LlamaSettings
from llama_index.embeddings.huggingface import HuggingFaceEmbedding

from app.config import get_settings
from app.services.projects import ProjectStore

settings = get_settings()


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
        except Exception as e:
            print(f"Error loading index: {e}, creating new one.")
            return VectorStoreIndex([])

    async def process_document(self, file_content: bytes, filename: str, project_id: str) -> str:
        """Process and index a document into a specific project."""
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

        return doc.doc_id

    def _extract_text_from_pdf(self, file_content: bytes) -> str:
        with fitz.open(stream=file_content, filetype="pdf") as doc:
            text = ""
            for page in doc:
                text += page.get_text()
        return text

    def _extract_text_from_txt(self, file_content: bytes) -> str:
        return file_content.decode("utf-8", errors="ignore")

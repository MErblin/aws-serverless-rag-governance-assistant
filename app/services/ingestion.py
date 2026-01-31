"""
DocuChat RAG - Document Ingestion Service

Handles document loading, parsing, chunking, and vector indexing.
"""

import os
from pathlib import Path
import fitz  # PyMuPDF
from llama_index.core import Document, VectorStoreIndex, StorageContext, load_index_from_storage
from llama_index.core.node_parser import SentenceSplitter
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.core import Settings as LlamaSettings

from app.config import get_settings

settings = get_settings()


class IngestionService:
    """
    Service for processing and indexing documents.
    """

    def __init__(self) -> None:
        """Initialize the ingestion service and load existing index if available."""
        self.storage_dir = settings.chroma_path
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        
        # Configure LlamaIndex to use local embedding model
        # We set this globally for the process
        LlamaSettings.embed_model = HuggingFaceEmbedding(
            model_name=settings.embedding_model
        )
        
        self.index = self._load_or_create_index()

    def _load_or_create_index(self) -> VectorStoreIndex:
        """Load existing index from storage or create a new one."""
        try:
            if (self.storage_dir / "docstore.json").exists():
                storage_context = StorageContext.from_defaults(persist_dir=str(self.storage_dir))
                return load_index_from_storage(storage_context)
            else:
                return VectorStoreIndex([])
        except Exception as e:
            print(f"Error loading index: {e}, creating new one.")
            return VectorStoreIndex([])

    async def process_document(self, file_content: bytes, filename: str) -> str:
        """Process and index a document."""
        # 1. Extract text
        file_ext = filename.split(".")[-1].lower()
        text = ""
        
        if file_ext == "pdf":
            text = self._extract_text_from_pdf(file_content)
        elif file_ext == "txt":
            text = self._extract_text_from_txt(file_content)
        else:
            raise ValueError(f"Unsupported file type: {file_ext}")

        # 2. Create Document
        doc = Document(
            text=text,
            metadata={"filename": filename, "file_type": file_ext}
        )

        # 3. Insert into Index (handling chunking functionality)
        self.index.insert(doc)
        
        # 4. Persist to disk
        self.index.storage_context.persist(persist_dir=str(self.storage_dir))
        
        return doc.doc_id

    def _extract_text_from_pdf(self, file_content: bytes) -> str:
        """Extract text content from a PDF file."""
        with fitz.open(stream=file_content, filetype="pdf") as doc:
            text = ""
            for page in doc:
                text += page.get_text()
        return text

    def _extract_text_from_txt(self, file_content: bytes) -> str:
        """Extract text content from a TXT file."""
        return file_content.decode("utf-8")

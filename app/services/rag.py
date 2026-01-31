"""
DocuChat RAG - RAG Query Service

Handles retrieval and generation using LlamaIndex.
"""

from llama_index.core import VectorStoreIndex, StorageContext, load_index_from_storage
from llama_index.core import Settings as LlamaSettings
from llama_index.llms.ollama import Ollama
from llama_index.embeddings.huggingface import HuggingFaceEmbedding

from app.config import get_settings

settings = get_settings()


class RAGService:
    """
    Service for RAG-based document querying.
    """

    def __init__(self) -> None:
        """Initialize the RAG service."""
        self.storage_dir = settings.chroma_path
        
        # 1. Configure LLM (Ollama)
        LlamaSettings.llm = Ollama(
            model=settings.ollama_model,
            base_url=settings.ollama_base_url,
            request_timeout=120.0,
        )
        
        # 2. Configure Embedding Model
        LlamaSettings.embed_model = HuggingFaceEmbedding(
            model_name=settings.embedding_model
        )
        
        # 3. Load Index
        self.index = self._load_index()

    def _load_index(self) -> VectorStoreIndex:
        """Load index from storage."""
        try:
            if (self.storage_dir / "docstore.json").exists():
                storage_context = StorageContext.from_defaults(persist_dir=str(self.storage_dir))
                return load_index_from_storage(storage_context)
            else:
                return VectorStoreIndex([])
        except Exception as e:
            print(f"Error loading index in RAG Service: {e}")
            return VectorStoreIndex([])

    async def query(self, question: str) -> tuple[str, list[str]]:
        """
        Query documents and generate an answer.
        
        Args:
            question: User's natural language question.
            
        Returns:
            Tuple of (answer, source_references).
        """
        # Reload index to get latest documents if needed
        # In a production app, we might want to handle this more efficiently
        # but for MVP, reloading ensures we see new uploads.
        # Check if index is empty
        if self.index is None:
             self.index = self._load_index()
             
        # Create Query Engine
        query_engine = self.index.as_query_engine(
            streaming=False,
            similarity_top_k=3,
        )
        
        # Execute Query
        response = query_engine.query(question)
        
        # Parse Sources
        sources = []
        if response.source_nodes:
            for node in response.source_nodes:
                filename = node.metadata.get("filename", "unknown")
                sources.append(filename)
        
        # Doodle sources to unique list
        unique_sources = list(set(sources))
        
        return str(response), unique_sources

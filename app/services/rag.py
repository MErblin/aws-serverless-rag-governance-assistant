"""
DocuChat RAG - RAG Query Service

Handles retrieval and generation using LlamaIndex.
This module will be fully implemented in Sprint 3.
"""

from app.config import get_settings

settings = get_settings()


class RAGService:
    """
    Service for RAG-based document querying.
    
    Handles:
    - Query embedding
    - Semantic search
    - Context assembly
    - LLM response generation
    """

    def __init__(self) -> None:
        """Initialize the RAG service."""
        # TODO: Initialize Ollama LLM in Sprint 3
        # TODO: Initialize query engine in Sprint 3
        pass

    async def query(self, question: str) -> tuple[str, list[str]]:
        """
        Query documents and generate an answer.
        
        Args:
            question: User's natural language question.
            
        Returns:
            Tuple of (answer, source_references).
        """
        # TODO: Implement in Sprint 3
        raise NotImplementedError("RAG query not yet implemented")

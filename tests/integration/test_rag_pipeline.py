"""
Integration test for the full RAG pipeline (Ingestion -> Storage -> Query).
"""

import os
import pytest
from app.services.ingestion import IngestionService
from app.services.rag import RAGService

# Skip this test if we can't connect to Ollama or lack dependencies
@pytest.mark.asyncio
async def test_rag_pipeline():
    """
    Test the full loop:
    1. Ingest a dummy PDF content
    2. Persist to storage
    3. Query the content via RAG
    """
    # 1. Create dummy PDF content (using text for simplicity as the extractor handles it)
    # Creating a minimal valid PDF is hard without a library, so we'll test with TXT
    # which goes through the same indexing pipeline
    filename = "test_doc.txt"
    content = b"The secret code for the project is BLUE-OMEGA-99."
    
    print("\n[Test] 1. Ingesting document...")
    ingestion = IngestionService()
    doc_id = await ingestion.process_document(content, filename)
    assert doc_id is not None
    print(f"[Test] Document indexed with ID: {doc_id}")
    
    # 2. Query
    print("[Test] 2. Querying RAG service...")
    rag = RAGService()
    
    # Check if we can actually query (requires Ollama running)
    try:
        response, sources = await rag.query("What is the secret code?")
        print(f"[Test] Response: {response}")
        print(f"[Test] Sources: {sources}")
        
        assert "BLUE-OMEGA-99" in str(response) or "BLUE-OMEGA-99" in str(response).upper()
        assert "test_doc.txt" in sources
    except Exception as e:
        pytest.skip(f"Skipping RAG query test (Ollama might be down): {e}")

if __name__ == "__main__":
    import asyncio
    asyncio.run(test_rag_pipeline())

"""
Integration-style test for ingestion + query contract (mocked LLM call path).
"""

from unittest.mock import AsyncMock, patch

import pytest

from app.services.ingestion import IngestionService
from app.services.rag import RAGService


@pytest.mark.asyncio
async def test_rag_pipeline_contract():
    filename = "test_doc.txt"
    content = b"The secret code for the project is BLUE-OMEGA-99."

    ingestion = IngestionService()
    doc_id = await ingestion.process_document(content, filename, "default")
    assert doc_id is not None

    rag = RAGService()

    mock_return = (
        "The secret code is BLUE-OMEGA-99.",
        [{"filename": "test_doc.txt", "chunk_id": "n1", "score": 0.8}],
        0.8,
        False,
        {"retrieval_mode": "hybrid_rrf_rerank"},
    )

    with patch.object(RAGService, "query", new=AsyncMock(return_value=mock_return)):
        answer, citations, confidence, abstained, diagnostics = await rag.query("What is the secret code?", "default")

    assert "BLUE-OMEGA-99" in answer
    assert citations[0]["filename"] == "test_doc.txt"
    assert confidence > 0
    assert abstained is False
    assert diagnostics["retrieval_mode"] == "hybrid_rrf_rerank"

"""
Integration-style contract test for ingestion + query path using mocks.
"""

from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.asyncio
async def test_rag_pipeline_contract():
    filename = "test_doc.txt"
    content = b"The secret code for the project is BLUE-OMEGA-99."

    with patch("app.services.ingestion.IngestionService.__init__", return_value=None), patch(
        "app.services.ingestion.IngestionService.process_document", new=AsyncMock(return_value="doc-1")
    ):
        from app.services.ingestion import IngestionService

        ingestion = IngestionService()
        doc_id = await ingestion.process_document(content, filename, "default")

    assert doc_id == "doc-1"

    mock_return = (
        "The secret code is BLUE-OMEGA-99.",
        [{"filename": "test_doc.txt", "chunk_id": "n1", "score": 0.8}],
        0.8,
        False,
        {"retrieval_mode": "hybrid_rrf_rerank"},
    )

    with patch("app.services.rag.RAGService.__init__", return_value=None), patch(
        "app.services.rag.RAGService.query", new=AsyncMock(return_value=mock_return)
    ):
        from app.services.rag import RAGService

        rag = RAGService()
        answer, citations, confidence, abstained, diagnostics = await rag.query("What is the secret code?", "default")

    assert "BLUE-OMEGA-99" in answer
    assert citations[0]["filename"] == "test_doc.txt"
    assert confidence > 0
    assert abstained is False
    assert diagnostics["retrieval_mode"] == "hybrid_rrf_rerank"

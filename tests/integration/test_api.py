"""
Integration tests for FastAPI endpoints (dependency-light via mocks).
"""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


class TestHealthEndpoint:
    def test_health_returns_200(self, client):
        response = client.get("/api/health")
        assert response.status_code == 200

    def test_health_returns_correct_structure(self, client):
        response = client.get("/api/health")
        data = response.json()
        assert data["status"] == "healthy"
        assert "version" in data


class TestRootEndpoint:
    def test_root_returns_200(self, client):
        response = client.get("/")
        assert response.status_code == 200

    def test_root_contains_welcome_message(self, client):
        response = client.get("/")
        data = response.json()
        assert "DocuChat" in data["message"]


class TestUploadEndpoint:
    def test_upload_valid_txt_file(self, client):
        with patch("app.services.ingestion.IngestionService.__init__", return_value=None), patch(
            "app.services.ingestion.IngestionService.process_document", new=AsyncMock(return_value="doc-123")
        ):
            files = {"file": ("test.txt", b"Hello, world!", "text/plain")}
            response = client.post("/api/upload", files=files)

        assert response.status_code == 200
        data = response.json()
        assert data["document_id"] == "doc-123"
        assert data["filename"] == "test.txt"
        assert data["project_id"] == "default"

    def test_upload_invalid_file_type(self, client):
        files = {"file": ("test.exe", b"binary", "application/octet-stream")}
        response = client.post("/api/upload", files=files)
        assert response.status_code == 400
        assert "Unsupported file type" in response.json()["detail"]

    def test_upload_no_file(self, client):
        response = client.post("/api/upload")
        assert response.status_code == 422


class TestQueryEndpoint:
    def test_query_valid_question(self, client):
        mock_result = (
            "Test answer",
            [{"filename": "test.txt", "chunk_id": "c1", "score": 0.91}],
            0.91,
            False,
            {"retrieval_mode": "hybrid_rrf_rerank"},
        )
        with patch("app.services.rag.RAGService.__init__", return_value=None), patch(
            "app.services.rag.RAGService.query", new=AsyncMock(return_value=mock_result)
        ):
            response = client.post(
                "/api/query",
                json={"question": "What is this document about?", "include_diagnostics": True},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["answer"] == "Test answer"
        assert "citations" in data
        assert data["project_id"] == "default"
        assert data["diagnostics"]["retrieval_mode"] == "hybrid_rrf_rerank"

    def test_query_empty_question(self, client):
        response = client.post("/api/query", json={"question": ""})
        assert response.status_code == 422

    def test_query_missing_question(self, client):
        response = client.post("/api/query", json={})
        assert response.status_code == 422

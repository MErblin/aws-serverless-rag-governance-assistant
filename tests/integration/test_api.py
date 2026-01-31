"""
Integration tests for the FastAPI endpoints.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    return TestClient(app)


class TestHealthEndpoint:
    """Tests for the /api/health endpoint."""

    def test_health_returns_200(self, client):
        """Test that health check returns 200 OK."""
        response = client.get("/api/health")
        
        assert response.status_code == 200

    def test_health_returns_correct_structure(self, client):
        """Test that health check returns expected fields."""
        response = client.get("/api/health")
        data = response.json()
        
        assert "status" in data
        assert "version" in data
        assert data["status"] == "healthy"


class TestRootEndpoint:
    """Tests for the root endpoint."""

    def test_root_returns_200(self, client):
        """Test that root endpoint returns 200 OK."""
        response = client.get("/")
        
        assert response.status_code == 200

    def test_root_contains_welcome_message(self, client):
        """Test that root endpoint returns welcome message."""
        response = client.get("/")
        data = response.json()
        
        assert "message" in data
        assert "DocuChat" in data["message"]


class TestUploadEndpoint:
    """Tests for the /api/upload endpoint."""

    def test_upload_valid_txt_file(self, client):
        """Test uploading a valid TXT file."""
        files = {"file": ("test.txt", b"Hello, world!", "text/plain")}
        response = client.post("/api/upload", files=files)
        
        assert response.status_code == 200
        data = response.json()
        assert "document_id" in data
        assert data["filename"] == "test.txt"

    def test_upload_invalid_file_type(self, client):
        """Test that invalid file types are rejected."""
        files = {"file": ("test.exe", b"binary content", "application/octet-stream")}
        response = client.post("/api/upload", files=files)
        
        assert response.status_code == 400
        assert "Unsupported file type" in response.json()["detail"]

    def test_upload_no_file(self, client):
        """Test that missing file returns error."""
        response = client.post("/api/upload")
        
        assert response.status_code == 422  # Validation error


class TestQueryEndpoint:
    """Tests for the /api/query endpoint."""

    def test_query_valid_question(self, client):
        """Test querying with a valid question."""
        response = client.post(
            "/api/query",
            json={"question": "What is this document about?"},
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "answer" in data
        assert "sources" in data

    def test_query_empty_question(self, client):
        """Test that empty question is rejected."""
        response = client.post("/api/query", json={"question": ""})
        
        assert response.status_code == 422  # Validation error

    def test_query_missing_question(self, client):
        """Test that missing question field is rejected."""
        response = client.post("/api/query", json={})
        
        assert response.status_code == 422  # Validation error

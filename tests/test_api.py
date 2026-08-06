"""NeuroForge API Tests.

Test suite for the FastAPI backend endpoints.
Run with: pytest tests/ -v

Note: These tests require the API to be running for full functionality.
Some tests use TestClient which doesn't initialize lifespan components.
"""

import pytest
from fastapi.testclient import TestClient

from main import app


@pytest.fixture
def client():
    """Create test client."""
    # Note: TestClient doesn't run lifespan events by default
    # For full tests, run against a running server
    return TestClient(app)


class TestHealthEndpoints:
    """Test health check endpoints."""

    def test_root(self, client):
        """Test root endpoint returns API info."""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "NeuroForge API"
        assert "version" in data
        assert "docs" in data

    def test_health(self, client):
        """Test health endpoint returns component status."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        # Without lifespan, components are None
        assert data["status"] in ["healthy", "degraded"]
        assert "components" in data


@pytest.mark.skipif(True, reason="Requires running server with lifespan")
class TestLiveEndpoints:
    """Tests that require a running server.
    
    Run these against a live server:
    pytest tests/test_api.py -v -m "not skipif"
    """

    def test_stats(self, client):
        """Test stats endpoint returns knowledge base info."""
        response = client.get("/stats")
        assert response.status_code == 200
        data = response.json()
        assert "knowledge_base" in data
        assert "learning" in data
        assert "chunks" in data["knowledge_base"]
        assert "concepts" in data["knowledge_base"]


class TestValidation:
    """Test input validation - doesn't require lifespan."""

    def test_quiz_missing_topic(self, client):
        """Test quiz without topic fails validation."""
        response = client.post(
            "/quiz",
            json={"num_questions": 5}  # Missing required 'topic'
        )
        assert response.status_code == 422  # Validation error

    def test_flashcard_missing_topic(self, client):
        """Test flashcard without topic fails validation."""
        response = client.post(
            "/flashcards",
            json={"num_cards": 5}  # Missing required 'topic'
        )
        assert response.status_code == 422

    def test_chat_missing_message(self, client):
        """Test chat without message fails validation."""
        response = client.post(
            "/chat",
            json={}  # Missing required 'message'
        )
        assert response.status_code == 422

    def test_solution_missing_question(self, client):
        """Test solution without question fails validation."""
        response = client.post(
            "/solution",
            json={"marks": 5}  # Missing required 'question'
        )
        assert response.status_code == 422


class TestEndpointStructure:
    """Test endpoint availability and structure."""

    def test_docs_available(self, client):
        """Test OpenAPI docs are available."""
        response = client.get("/docs")
        assert response.status_code == 200

    def test_openapi_json(self, client):
        """Test OpenAPI schema is accessible."""
        response = client.get("/openapi.json")
        assert response.status_code == 200
        data = response.json()
        assert "openapi" in data
        assert "paths" in data
        
        # Verify key endpoints exist
        paths = data["paths"]
        assert "/" in paths
        assert "/health" in paths
        assert "/upload" in paths
        assert "/quiz" in paths
        assert "/flashcards" in paths
        assert "/chat" in paths
        assert "/notes" in paths
        assert "/solution" in paths
        assert "/mindmap" in paths
        assert "/progress" in paths

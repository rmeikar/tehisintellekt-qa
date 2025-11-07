"""
Unit tests for FastAPI application.
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, AsyncMock, patch
from app import app
from models import PageSummary, AskResponse, UsageInfo


@pytest.fixture
def mock_indexer_and_processor():
    """Mock the global indexer and processor"""
    with patch('app.indexer') as mock_indexer, \
         patch('app.processor') as mock_processor:
        
        # Setup mock indexer
        mock_indexer.summaries = {
            "https://example.com": PageSummary(
                topics=["Test"],
                key_points=["Point"],
                potential_questions=["Question?"],
                summary="Summary"
            )
        }
        mock_indexer.full_content = {
            "https://example.com": "Test content"
        }
        mock_indexer.get_source_info = Mock(return_value={
            "https://example.com": {
                "summary": "Summary",
                "topics": ["Test"],
                "key_points": ["Point"],
                "content_preview": "Test content..."
            }
        })
        
        # Setup mock processor
        mock_processor.ask = AsyncMock(return_value=AskResponse(
            user_question="Test question",
            answer="Test answer",
            usage=UsageInfo(input_tokens=100, output_tokens=50),
            sources=["https://example.com"]
        ))
        
        yield mock_indexer, mock_processor


def test_root_endpoint():
    """Test root endpoint"""
    client = TestClient(app)
    response = client.get("/")
    
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert "endpoints" in data


def test_health_check():
    """Test health check endpoint"""
    client = TestClient(app)
    response = client.get("/health")
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"


def test_source_info_endpoint(mock_indexer_and_processor):
    """Test /source_info endpoint"""
    client = TestClient(app)
    response = client.get("/source_info")
    
    assert response.status_code == 200
    data = response.json()
    assert "https://example.com" in data
    assert data["https://example.com"]["summary"] == "Summary"


def test_source_info_not_initialized():
    """Test /source_info when indexer not initialized"""
    with patch('app.indexer', None):
        client = TestClient(app)
        response = client.get("/source_info")
        
        assert response.status_code == 503


def test_ask_endpoint(mock_indexer_and_processor):
    """Test /ask endpoint"""
    client = TestClient(app)
    response = client.post("/ask", json={"question": "What is AI?"})
    
    assert response.status_code == 200
    data = response.json()
    assert data["user_question"] == "Test question"
    assert data["answer"] == "Test answer"
    assert "usage" in data
    assert "sources" in data


def test_ask_endpoint_validation():
    """Test /ask endpoint input validation"""
    client = TestClient(app)
    
    # Empty question
    response = client.post("/ask", json={"question": ""})
    assert response.status_code == 422


def test_ask_not_initialized():
    """Test /ask when processor not initialized"""
    with patch('app.processor', None):
        client = TestClient(app)
        response = client.post("/ask", json={"question": "Test"})
        
        assert response.status_code == 503


def test_ask_processor_error(mock_indexer_and_processor):
    """Test /ask when processor raises error"""
    mock_indexer, mock_processor = mock_indexer_and_processor
    mock_processor.ask = AsyncMock(side_effect=Exception("Processing error"))
    
    client = TestClient(app)
    response = client.post("/ask", json={"question": "What is AI?"})
    
    assert response.status_code == 500


def test_cors_headers():
    """Test CORS headers are present"""
    client = TestClient(app)
    response = client.options("/", headers={"Origin": "http://example.com"})
    
    # CORS middleware should add headers
    assert "access-control-allow-origin" in response.headers

"""
Unit tests for query processor module.
"""
import pytest
from unittest.mock import Mock, AsyncMock
from processor import QueryProcessor
from indexer import ContentIndexer
from models import PageSummary, AskResponse


@pytest.fixture
def mock_indexer():
    """Create mock ContentIndexer"""
    indexer = Mock(spec=ContentIndexer)
    indexer.summaries = {
        "https://example.com/page1": PageSummary(
            topics=["AI", "Technology"],
            key_points=["AI is important", "Technology advances"],
            potential_questions=["What is AI?"],
            summary="Page about AI"
        ),
        "https://example.com/page2": PageSummary(
            topics=["Machine Learning"],
            key_points=["ML is a subset of AI"],
            potential_questions=["What is ML?"],
            summary="Page about ML"
        )
    }
    indexer.full_content = {
        "https://example.com/page1": "This is page 1 content about AI and technology.",
        "https://example.com/page2": "This is page 2 content about machine learning."
    }
    return indexer


@pytest.fixture
def mock_openai_client():
    """Create mock OpenAI client"""
    client = Mock()
    client.chat = Mock()
    client.chat.completions = Mock()
    return client


@pytest.fixture
def processor(mock_indexer, mock_openai_client):
    """Create QueryProcessor with mocks"""
    proc = QueryProcessor(indexer=mock_indexer, api_key="test-key")
    proc.client = mock_openai_client
    return proc


@pytest.mark.asyncio
async def test_find_relevant_pages_success(processor, mock_openai_client):
    """Test successful page selection"""
    # Mock LLM response for page selection
    mock_response = Mock()
    mock_response.choices = [Mock()]
    mock_response.choices[0].message.content = """{
        "relevant_urls": ["https://example.com/page1"],
        "reasoning": "Page 1 is most relevant"
    }"""
    
    mock_openai_client.chat.completions.create = AsyncMock(return_value=mock_response)
    
    urls = await processor.find_relevant_pages("What is AI?")
    
    assert len(urls) == 1
    assert "https://example.com/page1" in urls


@pytest.mark.asyncio
async def test_find_relevant_pages_fallback(processor, mock_openai_client):
    """Test fallback when LLM returns invalid URLs"""
    # Mock LLM response with invalid URL
    mock_response = Mock()
    mock_response.choices = [Mock()]
    mock_response.choices[0].message.content = """{
        "relevant_urls": ["https://invalid.com"],
        "reasoning": "Invalid URL"
    }"""
    
    mock_openai_client.chat.completions.create = AsyncMock(return_value=mock_response)
    
    urls = await processor.find_relevant_pages("What is AI?")
    
    # Should fallback to all pages
    assert len(urls) == 2


@pytest.mark.asyncio
async def test_find_relevant_pages_error_handling(processor, mock_openai_client):
    """Test error handling in page selection"""
    # Mock LLM error
    mock_openai_client.chat.completions.create = AsyncMock(
        side_effect=Exception("API Error")
    )
    
    urls = await processor.find_relevant_pages("What is AI?")
    
    # Should fallback to all pages on error
    assert len(urls) == 2


def test_build_context_basic(processor):
    """Test basic context building"""
    urls = ["https://example.com/page1", "https://example.com/page2"]
    context = processor.build_context(urls, max_chars=1000)
    
    assert "https://example.com/page1" in context
    assert "https://example.com/page2" in context
    assert "AI and technology" in context
    assert "machine learning" in context


def test_build_context_respects_limit(processor):
    """Test that context respects character limit"""
    urls = ["https://example.com/page1", "https://example.com/page2"]
    context = processor.build_context(urls, max_chars=50)
    
    # Allow overhead for [Source: URL]\n formatting per source (~30+ chars each)
    # With 2 URLs and content, expect ~125-150 chars total
    assert len(context) <= 200  # Reasonable upper bound with formatting


def test_build_context_skips_invalid_urls(processor):
    """Test that invalid URLs are skipped"""
    urls = ["https://example.com/page1", "https://invalid.com"]
    context = processor.build_context(urls, max_chars=1000)
    
    assert "https://example.com/page1" in context
    assert "https://invalid.com" not in context


@pytest.mark.asyncio
async def test_generate_answer_success(processor, mock_openai_client):
    """Test successful answer generation"""
    # Mock LLM response
    mock_response = Mock()
    mock_response.choices = [Mock()]
    mock_response.choices[0].message.content = """{
        "answer": "AI stands for Artificial Intelligence",
        "confidence": 0.95,
        "sources_used": ["https://example.com/page1"]
    }"""
    mock_response.usage = Mock()
    mock_response.usage.prompt_tokens = 100
    mock_response.usage.completion_tokens = 50
    
    mock_openai_client.chat.completions.create = AsyncMock(return_value=mock_response)
    
    response = await processor.generate_answer(
        "What is AI?",
        "Context about AI",
        ["https://example.com/page1"]
    )
    
    assert isinstance(response, AskResponse)
    assert "Artificial Intelligence" in response.answer
    assert response.usage.input_tokens == 100
    assert response.usage.output_tokens == 50
    assert len(response.sources) > 0


@pytest.mark.asyncio
async def test_generate_answer_error_handling(processor, mock_openai_client):
    """Test error handling in answer generation"""
    # Mock LLM error
    mock_openai_client.chat.completions.create = AsyncMock(
        side_effect=Exception("API Error")
    )
    
    response = await processor.generate_answer(
        "What is AI?",
        "Context",
        ["https://example.com/page1"]
    )
    
    assert isinstance(response, AskResponse)
    assert "Error" in response.answer


@pytest.mark.asyncio
async def test_ask_integration(processor, mock_openai_client):
    """Test full ask flow"""
    # Mock page selection
    selection_response = Mock()
    selection_response.choices = [Mock()]
    selection_response.choices[0].message.content = """{
        "relevant_urls": ["https://example.com/page1"],
        "reasoning": "Relevant"
    }"""
    
    # Mock answer generation
    answer_response = Mock()
    answer_response.choices = [Mock()]
    answer_response.choices[0].message.content = """{
        "answer": "Test answer",
        "confidence": 0.9,
        "sources_used": ["https://example.com/page1"]
    }"""
    answer_response.usage = Mock()
    answer_response.usage.prompt_tokens = 100
    answer_response.usage.completion_tokens = 50
    
    # Configure mock to return different responses
    mock_openai_client.chat.completions.create = AsyncMock(
        side_effect=[selection_response, answer_response]
    )
    
    response = await processor.ask("What is AI?")
    
    assert isinstance(response, AskResponse)
    assert response.user_question == "What is AI?"
    assert "Test answer" in response.answer
    assert response.usage.input_tokens == 100

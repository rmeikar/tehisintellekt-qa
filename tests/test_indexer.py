"""
Unit tests for indexer module.
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch
from indexer import ContentIndexer
from models import PageSummary, Page


@pytest.fixture
def mock_openai_client():
    """Create mock OpenAI client"""
    client = Mock()
    client.chat = Mock()
    client.chat.completions = Mock()
    return client


@pytest.fixture
def indexer(mock_openai_client):
    """Create ContentIndexer with mocked OpenAI client"""
    indexer = ContentIndexer(api_key="test-key")
    indexer.client = mock_openai_client
    return indexer


@pytest.mark.asyncio
async def test_generate_summary_success(indexer, mock_openai_client):
    """Test successful summary generation"""
    # Mock OpenAI response
    mock_response = Mock()
    mock_response.choices = [Mock()]
    mock_response.choices[0].message.content = """{
        "topics": ["AI", "Machine Learning"],
        "key_points": ["Point 1", "Point 2"],
        "potential_questions": ["What is AI?"],
        "summary": "Test summary"
    }"""
    # Mock usage tracking
    mock_response.usage = Mock()
    mock_response.usage.prompt_tokens = 100
    mock_response.usage.completion_tokens = 50
    
    mock_openai_client.chat.completions.create = AsyncMock(return_value=mock_response)
    
    summary = await indexer.generate_summary(
        "https://example.com",
        "Test content about AI and machine learning"
    )
    
    assert isinstance(summary, PageSummary)
    assert "AI" in summary.topics
    assert len(summary.key_points) > 0
    assert summary.summary == "Test summary"


@pytest.mark.asyncio
async def test_generate_summary_error_handling(indexer, mock_openai_client):
    """Test error handling in summary generation"""
    # Mock OpenAI error
    mock_openai_client.chat.completions.create = AsyncMock(
        side_effect=Exception("API Error")
    )
    
    summary = await indexer.generate_summary(
        "https://example.com",
        "Test content"
    )
    
    # Should return minimal summary on error
    assert isinstance(summary, PageSummary)
    assert "Error processing page" in summary.topics


@pytest.mark.asyncio
async def test_index_site_basic(indexer):
    """Test basic site indexing"""
    # Mock crawler
    mock_crawler = Mock()
    mock_page = Page(
        url="https://example.com",
        html="<html><body><p>This is a test page with enough content to be indexed. "
             "It needs to have at least 100 characters of clean text to pass the minimum content threshold. "
             "This additional text ensures the page will be processed and not skipped.</p></body></html>"
    )
    mock_crawler.crawl_site = AsyncMock(return_value=[mock_page])
    indexer.crawler = mock_crawler
    
    # Mock summary generation
    indexer.generate_summary = AsyncMock(
        return_value=PageSummary(
            topics=["Test"],
            key_points=["Key point"],
            potential_questions=["Question?"],
            summary="Summary"
        )
    )
    
    await indexer.index_site("https://example.com")
    
    assert len(indexer.summaries) == 1
    assert len(indexer.full_content) == 1
    assert "https://example.com" in indexer.summaries


@pytest.mark.asyncio
async def test_index_site_skips_short_content(indexer):
    """Test that pages with insufficient content are skipped"""
    # Mock crawler
    mock_crawler = Mock()
    mock_page = Page(
        url="https://example.com",
        html="<html><body><p>Short</p></body></html>"
    )
    mock_crawler.crawl_site = AsyncMock(return_value=[mock_page])
    indexer.crawler = mock_crawler
    
    await indexer.index_site("https://example.com")
    
    # Should skip page with too little content
    assert len(indexer.summaries) == 0


def test_get_source_info(indexer):
    """Test source info formatting"""
    # Add test data
    test_content = "Full content " * 100
    indexer.full_content["https://example.com"] = test_content
    indexer.summaries["https://example.com"] = PageSummary(
        topics=["Topic 1", "Topic 2"],
        key_points=["Point 1", "Point 2"],
        potential_questions=["Question?"],
        summary="Test summary"
    )
    
    source_info = indexer.get_source_info()
    
    # get_source_info returns {url: content} mapping
    assert "https://example.com" in source_info
    assert source_info["https://example.com"] == test_content
    assert isinstance(source_info["https://example.com"], str)


def test_get_source_info_empty(indexer):
    """Test source info with no indexed pages"""
    source_info = indexer.get_source_info()
    assert source_info == {}

"""
Unit tests for crawler module.
"""
import pytest
from pytest_httpx import HTTPXMock
from crawler import Crawler, TextCleaner
from models import Page


@pytest.fixture
def assert_all_responses_were_requested() -> bool:
    """Default fixture to assert all mocked responses are used."""
    return True


@pytest.mark.asyncio
async def test_crawler_basic(httpx_mock: HTTPXMock):
    """Test basic crawling functionality"""
    # Mock HTTP responses
    httpx_mock.add_response(
        url="https://example.com",
        html="""
        <html>
            <body>
                <a href="/page1">Page 1</a>
                <a href="/page2">Page 2</a>
                <p>Test content</p>
            </body>
        </html>
        """
    )
    httpx_mock.add_response(
        url="https://example.com/page1",
        html="<html><body><p>Page 1 content</p></body></html>"
    )
    httpx_mock.add_response(
        url="https://example.com/page2",
        html="<html><body><p>Page 2 content</p></body></html>"
    )
    
    crawler = Crawler(max_pages=10)
    pages = await crawler.crawl_site("https://example.com")
    
    assert len(pages) >= 1
    assert all(isinstance(page, Page) for page in pages)
    assert all(page.url.startswith("https://example.com") for page in pages)


@pytest.mark.asyncio
async def test_crawler_domain_restriction(httpx_mock: HTTPXMock):
    """Test that crawler stays within the same domain"""
    httpx_mock.add_response(
        url="https://example.com",
        html="""
        <html>
            <body>
                <a href="/internal">Internal</a>
                <a href="https://external.com">External</a>
            </body>
        </html>
        """
    )
    httpx_mock.add_response(
        url="https://example.com/internal",
        html="<html><body>Internal page</body></html>"
    )
    
    crawler = Crawler(max_pages=10)
    pages = await crawler.crawl_site("https://example.com")
    
    # Should not visit external.com
    urls = [page.url for page in pages]
    assert not any("external.com" in url for url in urls)


@pytest.mark.asyncio
async def test_crawler_max_pages_limit(httpx_mock: HTTPXMock):
    """Test that crawler respects max_pages limit"""
    # Mock exactly 5 pages with links to more pages
    # The crawler should stop at 5 even though links suggest more exist
    for i in range(5):
        httpx_mock.add_response(
            url=f"https://example.com/page{i}",
            html=f"<html><body><p>Page {i} content</p><a href='/page{i+1}'>Next</a></body></html>"
        )
    
    crawler = Crawler(max_pages=5)
    pages = await crawler.crawl_site("https://example.com/page0")
    
    # Should fetch exactly 5 pages and not follow the link to page5
    assert len(pages) == 5
    assert pages[0].url == "https://example.com/page0"
    assert pages[4].url == "https://example.com/page4"


def test_crawler_should_skip_url():
    """Test URL filtering logic"""
    crawler = Crawler()
    
    assert crawler._should_skip_url("https://example.com/file.pdf")
    assert crawler._should_skip_url("https://example.com/image.jpg")
    assert crawler._should_skip_url("https://example.com/video.mp4")
    assert not crawler._should_skip_url("https://example.com/page.html")
    assert not crawler._should_skip_url("https://example.com/page")


def test_text_cleaner_extract_text():
    """Test HTML text extraction"""
    html = """
    <html>
        <head><script>console.log('test')</script></head>
        <body>
            <nav>Navigation</nav>
            <header>Header</header>
            <main>
                <h1>Title</h1>
                <p>Content paragraph</p>
            </main>
            <footer>Footer</footer>
        </body>
    </html>
    """
    
    cleaner = TextCleaner()
    text = cleaner.extract_text(html)
    
    # Should contain main content
    assert "Title" in text
    assert "Content paragraph" in text
    
    # Should not contain unwanted elements
    assert "console.log" not in text
    assert "Navigation" not in text
    assert "Header" not in text
    assert "Footer" not in text


def test_text_cleaner_smart_truncate():
    """Test smart text truncation"""
    text = "A" * 1000 + "B" * 1000 + "C" * 1000
    cleaner = TextCleaner()
    
    truncated = cleaner.smart_truncate(text, max_chars=900)
    
    # Allow some overhead for separators (\n\n[...]\n\n appears twice = ~16-18 chars)
    assert len(truncated) <= 920
    assert "A" in truncated  # Should have start
    assert "C" in truncated  # Should have end
    assert "[...]" in truncated  # Should have separator


def test_text_cleaner_smart_truncate_no_truncation():
    """Test that short text is not truncated"""
    text = "Short text"
    cleaner = TextCleaner()
    
    truncated = cleaner.smart_truncate(text, max_chars=1000)
    
    assert truncated == text

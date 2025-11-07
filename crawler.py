"""
Web crawler for extracting content from tehisintellekt.ee
"""
import httpx
import asyncio
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, urlunparse, parse_qs, urlencode
from typing import List, Set, Dict
import json
from models import Page
import logging

logger = logging.getLogger(__name__)


class Crawler:
    """Asynchronous web crawler with domain restriction"""
    
    def __init__(self, max_pages: int = 100, timeout: int = 10, debug_log_path: str = "crawler_debug.json"):
        """
        Initialize crawler.
        
        Args:
            max_pages: Maximum number of pages to crawl
            timeout: HTTP request timeout in seconds
            debug_log_path: Path to save debug log
        """
        self.max_pages = max_pages
        self.timeout = timeout
        self.visited: Set[str] = set()
        self.debug_log_path = debug_log_path
        self.debug_info: Dict = {
            "filtered_urls": [],
            "normalized_urls": [],
            "crawled_urls": [],
            "skipped_duplicates": []
        }
        
    async def crawl_site(self, base_url: str) -> List[Page]:
        """
        Crawl website starting from base_url.
        
        Args:
            base_url: Starting URL for crawling
            
        Returns:
            List of Page objects containing URL and HTML content
        """
        to_visit = {base_url}
        pages = []
        base_domain = urlparse(base_url).netloc
        
        async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
            while to_visit and len(pages) < self.max_pages:
                url = to_visit.pop()
                
                if url in self.visited:
                    continue
                    
                self.visited.add(url)
                logger.info(f"Crawling: {url}")
                
                try:
                    response = await client.get(url)
                    
                    if response.status_code == 200 and 'text/html' in response.headers.get('content-type', ''):
                        pages.append(Page(url=url, html=response.text))
                        self.debug_info["crawled_urls"].append(url)
                        
                        # Extract and filter links
                        soup = BeautifulSoup(response.text, 'html.parser')
                        for link in soup.find_all('a', href=True):
                            full_url = urljoin(url, link['href'])
                            original_url = full_url
                            
                            # Normalize URL (remove fragments and UTM params)
                            normalized_url = self._normalize_url(full_url)
                            
                            if normalized_url != original_url:
                                self.debug_info["normalized_urls"].append({
                                    "original": original_url,
                                    "normalized": normalized_url
                                })
                            
                            # Only follow links within same domain
                            parsed = urlparse(normalized_url)
                            if parsed.netloc == base_domain:
                                if self._should_skip_url(normalized_url):
                                    self.debug_info["filtered_urls"].append({
                                        "url": normalized_url,
                                        "reason": "file_extension"
                                    })
                                elif normalized_url in self.visited:
                                    self.debug_info["skipped_duplicates"].append(normalized_url)
                                else:
                                    to_visit.add(normalized_url)
                                
                except httpx.HTTPError as e:
                    logger.warning(f"Error crawling {url}: {e}")
                except Exception as e:
                    logger.error(f"Unexpected error crawling {url}: {e}")
                    
                # Small delay to be respectful
                await asyncio.sleep(0.1)
        
        logger.info(f"Crawled {len(pages)} pages")
        
        # Save debug log
        self._save_debug_log()
        
        return pages
    
    def _normalize_url(self, url: str) -> str:
        """
        Normalize URL by removing fragments and UTM parameters.
        
        Args:
            url: URL to normalize
            
        Returns:
            Normalized URL
        """
        parsed = urlparse(url)
        
        # Remove fragment (everything after #)
        # Parse query parameters and remove UTM params
        query_params = parse_qs(parsed.query)
        
        # Remove UTM and tracking parameters
        utm_params = ['utm_source', 'utm_medium', 'utm_campaign', 'utm_content', 'utm_term']
        filtered_params = {k: v for k, v in query_params.items() if k not in utm_params}
        
        # Rebuild query string
        new_query = urlencode(filtered_params, doseq=True) if filtered_params else ''
        
        # Rebuild URL without fragment and with filtered query
        normalized = urlunparse((
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            parsed.params,
            new_query,
            ''  # No fragment
        ))
        
        return normalized
    
    def _should_skip_url(self, url: str) -> bool:
        """
        Check if URL should be skipped.
        
        Args:
            url: URL to check
            
        Returns:
            True if URL should be skipped
        """
        skip_extensions = {'.pdf', '.jpg', '.jpeg', '.png', '.gif', '.zip', '.mp4'}
        return any(url.lower().endswith(ext) for ext in skip_extensions)
    
    def _save_debug_log(self) -> None:
        """
        Save debug information to JSON file.
        """
        try:
            summary = {
                "total_crawled": len(self.debug_info["crawled_urls"]),
                "total_filtered": len(self.debug_info["filtered_urls"]),
                "total_normalized": len(self.debug_info["normalized_urls"]),
                "total_duplicates_skipped": len(self.debug_info["skipped_duplicates"]),
                "details": self.debug_info
            }
            
            with open(self.debug_log_path, 'w', encoding='utf-8') as f:
                json.dump(summary, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Debug log saved to {self.debug_log_path}")
            logger.info(f"Summary: {len(self.debug_info['crawled_urls'])} crawled, "
                       f"{len(self.debug_info['normalized_urls'])} normalized, "
                       f"{len(self.debug_info['skipped_duplicates'])} duplicates skipped")
        except Exception as e:
            logger.error(f"Failed to save debug log: {e}")


class TextCleaner:
    """Clean and extract text from HTML"""
    
    @staticmethod
    def extract_text(html: str) -> str:
        """
        Extract clean text from HTML content.
        
        Args:
            html: Raw HTML string
            
        Returns:
            Cleaned text content
        """
        soup = BeautifulSoup(html, 'html.parser')
        
        # Remove unwanted elements
        for element in soup(['script', 'style', 'nav', 'footer', 'header', 
                            'iframe', 'noscript', 'meta', 'link', 'button']):
            element.decompose()
        
        # Remove button-like links (CTA buttons)
        for button in soup.find_all('a', class_=lambda x: x and 'button' in x.lower()):
            button.decompose()
        
        # Get text with structure preservation
        text = soup.get_text(separator='\n', strip=True)
        
        # Clean up excessive whitespace
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        clean_text = '\n'.join(lines)
        
        return clean_text
    
    @staticmethod
    def smart_truncate(text: str, max_chars: int) -> str:
        """
        Intelligently truncate text to max_chars while preserving important parts.
        Takes content from beginning, middle, and end.
        
        Args:
            text: Text to truncate
            max_chars: Maximum characters
            
        Returns:
            Truncated text
        """
        if len(text) <= max_chars:
            return text
        
        # Take 40% from start, 20% from middle, 40% from end
        part_size = max_chars // 3
        start = text[:part_size]
        
        middle_idx = len(text) // 2
        middle = text[middle_idx - part_size // 2:middle_idx + part_size // 2]
        
        end = text[-part_size:]
        
        return f"{start}\n\n[...]\n\n{middle}\n\n[...]\n\n{end}"

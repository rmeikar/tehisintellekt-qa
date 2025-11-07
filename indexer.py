"""
Content indexing and LLM-based summarization.
"""
import json
import logging
import time
from typing import Dict, List
from openai import AsyncOpenAI
from models import Page, PageSummary
from crawler import Crawler, TextCleaner

logger = logging.getLogger(__name__)


class ContentIndexer:
    """Indexes website content and generates LLM summaries"""
    
    def __init__(self, api_key: str, debug_log_dir: str = "logs"):
        """
        Initialize indexer with OpenAI API key.
        
        Args:
            api_key: OpenAI API key
            debug_log_dir: Directory to save debug logs
        """
        self.client = AsyncOpenAI(api_key=api_key)
        self.summaries: Dict[str, PageSummary] = {}
        self.full_content: Dict[str, str] = {}
        
        # Token usage tracking
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        
        # Error tracking
        self.failed_summaries = []
        self.retry_successes = 0
        
        # Create logs directory if it doesn't exist
        import os
        os.makedirs(debug_log_dir, exist_ok=True)
        
        self.crawler = Crawler(debug_log_path=f"{debug_log_dir}/crawler_debug.json")
        self.text_cleaner = TextCleaner()
        
    async def index_site(self, base_url: str = "https://tehisintellekt.ee") -> None:
        """
        Crawl and index entire site.
        
        Args:
            base_url: Starting URL for crawling
        """
        start_time = time.time()
        logger.info(f"Starting indexing of {base_url}")
        
        # 1. Crawl the site
        pages = await self.crawler.crawl_site(base_url)
        logger.info(f"Crawled {len(pages)} pages")
        
        # 2. Process each page
        for page in pages:
            try:
                # Extract clean text
                clean_text = self.text_cleaner.extract_text(page.html)
                
                if len(clean_text.strip()) < 100:  # Skip pages with too little content
                    logger.debug(f"Skipping {page.url} - insufficient content")
                    continue
                
                self.full_content[page.url] = clean_text
                
                # Generate summary
                summary = await self.generate_summary(page.url, clean_text)
                self.summaries[page.url] = summary
                
                logger.info(f"Indexed: {page.url}")
                
            except Exception as e:
                logger.error(f"Error indexing {page.url}: {e}")
                
        elapsed_time = time.time() - start_time
        minutes = int(elapsed_time // 60)
        seconds = int(elapsed_time % 60)
        
        logger.info(f"Indexing complete. Processed {len(self.summaries)} pages")
        logger.info(f"")
        logger.info(f"📊 Indexing Summary:")
        logger.info(f"   Time taken:    {minutes}m {seconds}s")
        logger.info(f"   Input tokens:  {self.total_input_tokens:,}")
        logger.info(f"   Output tokens: {self.total_output_tokens:,}")
        logger.info(f"   Total tokens:  {self.total_input_tokens + self.total_output_tokens:,}")
        
        # Log error statistics
        if self.failed_summaries or self.retry_successes:
            logger.info(f"")
            logger.info(f"⚠️  Error Recovery:")
            if self.retry_successes > 0:
                logger.info(f"   Successful retries: {self.retry_successes}")
            if self.failed_summaries:
                logger.warning(f"   Failed summaries: {len(self.failed_summaries)}")
                logger.warning(f"   Failed URLs: {', '.join([url.split('/')[-2] + '/' + url.split('/')[-1] for url in self.failed_summaries])}")
        
        logger.info(f"")
    
    async def generate_summary(self, url: str, content: str, retry: int = 0) -> PageSummary:
        """
        Generate intelligent summary of page content using LLM.
        
        Args:
            url: Page URL
            content: Clean text content
            retry: Current retry attempt (internal use)
            
        Returns:
            PageSummary object with topics, key points, and summary
        """
        # Truncate content if too long
        truncated = self.text_cleaner.smart_truncate(content, max_chars=15000)
        
        try:
            response = await self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": """Analyze the page content and provide a structured summary.

YOU MUST include all four fields in your response:
1. topics: List of main themes (minimum 2)
2. key_points: Important facts (minimum 3)
3. potential_questions: Questions this page answers (minimum 2)
4. summary: A comprehensive paragraph summary (minimum 50 words)

All fields are required."""
                    },
                    {
                        "role": "user",
                        "content": f"URL: {url}\n\nContent:\n{truncated}"
                    }
                ],
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "summary",
                        "schema": {
                            "type": "object",
                            "properties": {
                                "topics": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                    "description": "Main topics covered",
                                    "minItems": 1
                                },
                                "key_points": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                    "description": "Key facts and information",
                                    "minItems": 1
                                },
                                "potential_questions": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                    "description": "Questions this page could answer",
                                    "minItems": 1
                                },
                                "summary": {
                                    "type": "string",
                                    "description": "Comprehensive summary of the page",
                                    "minLength": 20
                                }
                            },
                            "required": ["topics", "key_points", "potential_questions", "summary"],
                            "additionalProperties": False
                        }
                    }
                }
            )
            
            # Track token usage
            if response.usage:
                self.total_input_tokens += response.usage.prompt_tokens
                self.total_output_tokens += response.usage.completion_tokens
            
            summary_data = json.loads(response.choices[0].message.content)
            return PageSummary(**summary_data)
            
        except Exception as e:
            logger.error(f"Error generating summary for {url}: {e}")
            
            # Retry once on validation error
            if retry == 0 and "validation error" in str(e).lower():
                logger.warning(f"Retrying summary generation for {url} (attempt 2/2)")
                try:
                    result = await self.generate_summary(url, content, retry=1)
                    self.retry_successes += 1
                    return result
                except:
                    pass  # Fall through to minimal summary
            
            # Return minimal summary on error
            logger.warning(f"Falling back to minimal summary for {url}")
            self.failed_summaries.append(url)
            return PageSummary(
                topics=["Error processing page"],
                key_points=[],
                potential_questions=[],
                summary=content[:500]
            )
    
    def get_source_info(self) -> Dict[str, str]:
        """
        Get formatted source information for all indexed pages.
        
        Returns:
            Dictionary mapping URLs to their actual content (source text)
        """
        return {
            url: content
            for url, content in self.full_content.items()
        }

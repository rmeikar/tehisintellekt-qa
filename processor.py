"""
Query processing with LLM-based retrieval and answer generation.
"""
import json
import logging
from typing import List, Dict
from openai import AsyncOpenAI
from models import AskResponse, UsageInfo, PageSelection, AnswerGeneration
from indexer import ContentIndexer

logger = logging.getLogger(__name__)


class QueryProcessor:
    """Processes user queries using LLM-based retrieval"""
    
    def __init__(self, indexer: ContentIndexer, api_key: str):
        """
        Initialize query processor.
        
        Args:
            indexer: ContentIndexer instance with indexed pages
            api_key: OpenAI API key
        """
        self.indexer = indexer
        self.client = AsyncOpenAI(api_key=api_key)
        
    async def ask(self, question: str) -> AskResponse:
        """
        Process user question and generate answer.
        
        Args:
            question: User's question
            
        Returns:
            AskResponse with answer, usage, and sources
        """
        logger.info(f"Processing question: {question}")
        
        # Step 1: Find relevant pages using LLM
        relevant_urls = await self.find_relevant_pages(question)
        logger.info(f"Selected {len(relevant_urls)} relevant pages")
        
        # Step 2: Build context from selected pages
        context = self.build_context(relevant_urls, max_chars=180000)
        logger.debug(f"Built context of {len(context)} characters")
        
        # Step 3: Generate answer
        answer_response = await self.generate_answer(question, context, relevant_urls)
        
        return answer_response
    
    async def find_relevant_pages(self, question: str) -> List[str]:
        """
        Use LLM to select most relevant pages for answering the question.
        
        Args:
            question: User's question
            
        Returns:
            List of relevant URLs
        """
        # Prepare summaries for LLM selection
        summaries_text = "\n\n".join([
            f"URL: {url}\n"
            f"Summary: {data.summary}\n"
            f"Topics: {', '.join(data.topics)}\n"
            f"Key Points: {', '.join(data.key_points[:3])}"
            for url, data in self.indexer.summaries.items()
        ])
        
        try:
            response = await self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": """Analyze the question and select the most relevant pages to answer it.
Return URLs of pages that contain relevant information.
Be inclusive - if a page might be helpful, include it.
Prioritize pages that directly address the question's topic.
You can select multiple pages if they together provide a complete answer."""
                    },
                    {
                        "role": "user",
                        "content": f"Question: {question}\n\nAvailable pages:\n{summaries_text}"
                    }
                ],
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "selection",
                        "schema": {
                            "type": "object",
                            "properties": {
                                "relevant_urls": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                    "description": "List of relevant URLs"
                                },
                                "reasoning": {
                                    "type": "string",
                                    "description": "Explanation of selection"
                                }
                            },
                            "required": ["relevant_urls", "reasoning"],
                            "additionalProperties": False
                        }
                    }
                }
            )
            
            selection_data = json.loads(response.choices[0].message.content)
            selection = PageSelection(**selection_data)
            
            logger.debug(f"Page selection reasoning: {selection.reasoning}")
            
            # Filter to only include URLs we actually have
            valid_urls = [
                url for url in selection.relevant_urls 
                if url in self.indexer.full_content
            ]
            
            # If no valid URLs found, return all URLs as fallback
            if not valid_urls:
                logger.warning("No valid URLs from LLM selection, using all pages")
                return list(self.indexer.full_content.keys())
            
            return valid_urls
            
        except Exception as e:
            logger.error(f"Error in page selection: {e}")
            # Fallback: return all pages
            return list(self.indexer.full_content.keys())
    
    def build_context(self, urls: List[str], max_chars: int) -> str:
        """
        Build context from selected pages within character limit.
        
        Args:
            urls: List of URLs to include
            max_chars: Maximum characters (should be ~200k chars = ~50k tokens)
            
        Returns:
            Formatted context string
        """
        context_parts = []
        char_count = 0
        
        for url in urls:
            if url not in self.indexer.full_content:
                continue
                
            content = self.indexer.full_content[url]
            
            # Calculate available space
            available_space = max_chars - char_count
            if available_space <= 0:
                break
            
            # Add content or truncated version
            if len(content) <= available_space:
                context_parts.append(f"[Source: {url}]\n{content}\n")
                char_count += len(content)
            else:
                # Use smart truncation for partial content
                truncated = content[:available_space - 100]
                context_parts.append(f"[Source: {url}]\n{truncated}...\n")
                char_count += available_space
                break
        
        return "\n".join(context_parts)
    
    async def generate_answer(
        self, 
        question: str, 
        context: str, 
        sources: List[str]
    ) -> AskResponse:
        """
        Generate answer using LLM with provided context.
        
        Args:
            question: User's question
            context: Context from selected pages
            sources: List of source URLs
            
        Returns:
            AskResponse with answer and metadata
        """
        try:
            response = await self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": """Answer questions using ONLY the provided context.
If information is not in the context, clearly state you don't have that information.
Be specific and cite relevant information from the sources.
Respond in the same language as the question.
If question is in Estonian, answer in Estonian.
If question is in English, answer in English.
Provide comprehensive answers but stay grounded in the provided context."""
                    },
                    {
                        "role": "user",
                        "content": f"Context:\n{context}\n\nQuestion: {question}"
                    }
                ],
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "answer",
                        "schema": {
                            "type": "object",
                            "properties": {
                                "answer": {
                                    "type": "string",
                                    "description": "Detailed answer to the question"
                                },
                                "confidence": {
                                    "type": "number",
                                    "description": "Confidence level 0-1",
                                    "minimum": 0,
                                    "maximum": 1
                                },
                                "sources_used": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                    "description": "URLs actually used in the answer"
                                }
                            },
                            "required": ["answer", "confidence", "sources_used"],
                            "additionalProperties": False
                        }
                    }
                }
            )
            
            answer_data = json.loads(response.choices[0].message.content)
            answer_gen = AnswerGeneration(**answer_data)
            
            # Build response
            return AskResponse(
                user_question=question,
                answer=answer_gen.answer,
                usage=UsageInfo(
                    input_tokens=response.usage.prompt_tokens,
                    output_tokens=response.usage.completion_tokens
                ),
                sources=sources
            )
            
        except Exception as e:
            logger.error(f"Error generating answer: {e}")
            # Return error response
            return AskResponse(
                user_question=question,
                answer=f"Error generating answer: {str(e)}",
                usage=UsageInfo(input_tokens=0, output_tokens=0),
                sources=sources
            )

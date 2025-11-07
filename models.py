"""
Pydantic models for request/response validation.
"""
from pydantic import BaseModel, Field
from typing import List, Dict, Optional


class QuestionRequest(BaseModel):
    """Request model for /ask endpoint"""
    question: str = Field(..., description="User's question", min_length=1)


class UsageInfo(BaseModel):
    """Token usage information"""
    input_tokens: int = Field(..., description="Number of input tokens used")
    output_tokens: int = Field(..., description="Number of output tokens used")


class AskResponse(BaseModel):
    """Response model for /ask endpoint"""
    user_question: str = Field(..., description="Original user question")
    answer: str = Field(..., description="LLM generated answer")
    usage: UsageInfo = Field(..., description="Token usage statistics")
    sources: List[str] = Field(..., description="URLs used to generate the answer")


class PageSummary(BaseModel):
    """Summary of a single page"""
    topics: List[str]
    key_points: List[str]
    potential_questions: List[str]
    summary: str


class PageSelection(BaseModel):
    """LLM response for page selection"""
    relevant_urls: List[str]
    reasoning: str


class AnswerGeneration(BaseModel):
    """LLM response for answer generation"""
    answer: str
    confidence: float
    sources_used: List[str]


class Page(BaseModel):
    """Represents a crawled web page"""
    url: str
    html: str
    text: Optional[str] = None

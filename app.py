"""
FastAPI application for web-based conversational API.
"""
import os
import logging
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from models import QuestionRequest, AskResponse
from indexer import ContentIndexer
from processor import QueryProcessor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global instances
indexer: ContentIndexer = None
processor: QueryProcessor = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for startup and shutdown events.
    Crawls and indexes the website on startup.
    """
    global indexer, processor
    
    # Startup
    logger.info("Starting application...")
    
    # Get OpenAI API key from environment
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        logger.error("OPENAI_API_KEY environment variable is not set")
        logger.error("Please set your OpenAI API key in a .env file or environment variable")
        raise ValueError("OPENAI_API_KEY is required. See README for setup instructions.")
    
    # Initialize indexer and crawl site
    indexer = ContentIndexer(api_key=api_key)
    
    try:
        await indexer.index_site()
        logger.info(f"✓ Indexed {len(indexer.summaries)} pages successfully")
    except Exception as e:
        logger.error(f"✗ Error during indexing: {e}")
        raise
    
    # Initialize processor
    processor = QueryProcessor(indexer=indexer, api_key=api_key)
    logger.info("✓ Application started successfully")
    
    yield
    
    # Shutdown
    logger.info("Shutting down application...")


# Create FastAPI app
app = FastAPI(
    title="Tehisintellekt.ee Q&A API",
    description="Web-based conversational API that answers questions based on tehisintellekt.ee content",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "message": "Tehisintellekt.ee Q&A API",
        "version": "1.0.0",
        "endpoints": {
            "GET /source_info": "Get information about indexed sources",
            "POST /ask": "Ask a question based on indexed content"
        },
        "indexed_pages": len(indexer.summaries) if indexer else 0
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "indexed_pages": len(indexer.summaries) if indexer else 0
    }


@app.get("/source_info")
async def source_info():
    """
    Get information about all indexed sources.
    
    Returns:
        Dictionary mapping URLs to their summaries and metadata
    """
    if not indexer:
        raise HTTPException(status_code=503, detail="Indexer not initialized")
    
    if not indexer.summaries:
        raise HTTPException(status_code=503, detail="No pages indexed yet")
    
    return indexer.get_source_info()


@app.post("/ask", response_model=AskResponse)
async def ask(request: QuestionRequest) -> AskResponse:
    """
    Answer a question based on indexed content.
    
    Args:
        request: QuestionRequest with user's question
        
    Returns:
        AskResponse with answer, token usage, and sources
    """
    if not processor:
        raise HTTPException(status_code=503, detail="Processor not initialized")
    
    if not indexer.summaries:
        raise HTTPException(status_code=503, detail="No pages indexed yet")
    
    try:
        response = await processor.ask(request.question)
        logger.info(f"Answered question: {request.question[:50]}...")
        return response
    except Exception as e:
        logger.error(f"Error processing question: {e}")
        raise HTTPException(status_code=500, detail=f"Error processing question: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

"""
DocuChat RAG - API Routes

REST API endpoints for document upload and querying.
"""

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel, Field

from app.config import get_settings

router = APIRouter()
settings = get_settings()


# ============================================================================
# Request/Response Models
# ============================================================================

class QueryRequest(BaseModel):
    """Request model for document queries."""

    question: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="Question to ask about the uploaded documents",
        examples=["What is the main topic of this document?"],
    )


class QueryResponse(BaseModel):
    """Response model for document queries."""

    answer: str = Field(..., description="Generated answer from the RAG pipeline")
    sources: list[str] = Field(
        default_factory=list,
        description="Source document references used for the answer",
    )


class UploadResponse(BaseModel):
    """Response model for document uploads."""

    message: str = Field(..., description="Status message")
    document_id: str = Field(..., description="Unique identifier for the document")
    filename: str = Field(..., description="Original filename")


class HealthResponse(BaseModel):
    """Response model for health check."""

    status: str = Field(..., description="Service status")
    version: str = Field(..., description="Application version")


# ============================================================================
# Endpoints
# ============================================================================

@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """
    Health check endpoint.
    
    Returns the current status and version of the API.
    """
    return HealthResponse(
        status="healthy",
        version=settings.app_version,
    )


@router.post("/upload", response_model=UploadResponse)
async def upload_document(file: UploadFile = File(...)) -> UploadResponse:
    """
    Upload a document for processing and indexing.
    """
    # Validate file type
    allowed_types = [".pdf", ".txt"]
    filename = file.filename or "unknown"
    file_ext = "." + filename.split(".")[-1].lower() if "." in filename else ""
    
    if file_ext not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type. Allowed: {', '.join(allowed_types)}",
        )
    
    # Validate file size
    contents = await file.read()
    if len(contents) > settings.max_file_size_bytes:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum size: {settings.max_file_size_mb}MB",
        )
    
    try:
        from app.services.ingestion import IngestionService
        service = IngestionService()
        document_id = await service.process_document(contents, filename)
        
        return UploadResponse(
            message="Document uploaded and indexed successfully",
            document_id=document_id,
            filename=filename,
        )
    except Exception as e:
        print(f"Error processing document: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/query", response_model=QueryResponse)
async def query_documents(request: QueryRequest) -> QueryResponse:
    """
    Query the indexed documents.
    """
    try:
        from app.services.rag import RAGService
        service = RAGService()
        answer, sources = await service.query(request.question)
        
        return QueryResponse(
            answer=answer,
            sources=sources,
        )
    except Exception as e:
        print(f"Error querying documents: {e}")
        raise HTTPException(status_code=500, detail=str(e))

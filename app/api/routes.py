"""
DocuChat RAG - API Routes

REST API endpoints for project-based document upload and querying.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel, Field

from app.config import get_settings
from app.services.projects import ProjectStore

router = APIRouter()
settings = get_settings()
project_store = ProjectStore()
project_store.ensure_default_project()


class QueryRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=1000)
    include_diagnostics: bool = False


class ProjectCreateRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=80)
    description: str | None = ""
    system_prompt: str | None = None
    model: str | None = None
    top_k: int = Field(default=3, ge=1, le=20)
    chunk_size: int | None = Field(default=None, ge=100, le=4000)
    chunk_overlap: int | None = Field(default=None, ge=0, le=1000)


class ProjectUpdateRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    system_prompt: str | None = None
    model: str | None = None
    top_k: int | None = Field(default=None, ge=1, le=20)
    chunk_size: int | None = Field(default=None, ge=100, le=4000)
    chunk_overlap: int | None = Field(default=None, ge=0, le=1000)


class Citation(BaseModel):
    filename: str
    chunk_id: str
    score: float


class QueryResponse(BaseModel):
    answer: str
    citations: list[Citation] = Field(default_factory=list)
    confidence: float = 0.0
    abstained: bool = False
    project_id: str
    diagnostics: dict[str, Any] | None = None


class UploadResponse(BaseModel):
    message: str
    document_id: str
    filename: str
    project_id: str


class HealthResponse(BaseModel):
    status: str
    version: str


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    return HealthResponse(status="healthy", version=settings.app_version)


@router.post("/projects")
async def create_project(request: ProjectCreateRequest) -> dict[str, Any]:
    try:
        project = project_store.create_project(
            name=request.name,
            description=request.description,
            system_prompt=request.system_prompt,
            model=request.model,
            top_k=request.top_k,
            chunk_size=request.chunk_size,
            chunk_overlap=request.chunk_overlap,
        )
        return project
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/projects")
async def list_projects() -> list[dict[str, Any]]:
    return project_store.list_projects()


@router.get("/projects/{project_id}")
async def get_project(project_id: str) -> dict[str, Any]:
    project = project_store.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.patch("/projects/{project_id}")
async def update_project(project_id: str, request: ProjectUpdateRequest) -> dict[str, Any]:
    try:
        project = project_store.update_project(project_id, request.model_dump(exclude_none=True))
        return project
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/projects/{project_id}/upload", response_model=UploadResponse)
async def upload_document_to_project(project_id: str, file: UploadFile = File(...)) -> UploadResponse:
    allowed_types = [".pdf", ".txt"]
    filename = file.filename or "unknown"
    file_ext = "." + filename.split(".")[-1].lower() if "." in filename else ""

    if file_ext not in allowed_types:
        raise HTTPException(status_code=400, detail=f"Unsupported file type. Allowed: {', '.join(allowed_types)}")

    contents = await file.read()
    if len(contents) > settings.max_file_size_bytes:
        raise HTTPException(status_code=400, detail=f"File too large. Maximum size: {settings.max_file_size_mb}MB")

    try:
        from app.services.ingestion import IngestionService

        service = IngestionService()
        document_id = await service.process_document(contents, filename, project_id)

        return UploadResponse(
            message="Document uploaded and indexed successfully",
            document_id=document_id,
            filename=filename,
            project_id=project_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/projects/{project_id}/query", response_model=QueryResponse)
async def query_project_documents(project_id: str, request: QueryRequest) -> QueryResponse:
    try:
        from app.services.rag import RAGService

        service = RAGService()
        answer, citations, confidence, abstained, diagnostics = await service.query(
            request.question,
            project_id,
            include_diagnostics=request.include_diagnostics,
        )
        return QueryResponse(
            answer=answer,
            citations=[Citation(**c) for c in citations],
            confidence=confidence,
            abstained=abstained,
            project_id=project_id,
            diagnostics=diagnostics,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Backward-compatible endpoints mapped to default project
@router.post("/upload", response_model=UploadResponse)
async def upload_document(file: UploadFile = File(...)) -> UploadResponse:
    return await upload_document_to_project(settings.default_project_id, file)


@router.post("/query", response_model=QueryResponse)
async def query_documents(request: QueryRequest) -> QueryResponse:
    return await query_project_documents(settings.default_project_id, request)

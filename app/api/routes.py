"""
DocuChat RAG - API Routes

REST API endpoints for project-based document upload and querying.
"""

from __future__ import annotations

from typing import Any
import json
from datetime import datetime, timezone

from fastapi import APIRouter, File, HTTPException, UploadFile, Query
from pydantic import BaseModel, Field

from app.config import get_settings
from app.services.projects import ProjectStore

router = APIRouter()
settings = get_settings()
project_store = ProjectStore()
project_store.ensure_default_project()


def _logs_path(project_id: str):
    return project_store.get_project_paths(project_id)["project_dir"] / "query_logs.jsonl"


def _append_query_log(project_id: str, payload: dict[str, Any]) -> None:
    path = _logs_path(project_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload["timestamp"] = datetime.now(timezone.utc).isoformat()
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload) + "\n")


def _read_query_logs(project_id: str, limit: int = 50) -> list[dict[str, Any]]:
    path = _logs_path(project_id)
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    out: list[dict[str, Any]] = []
    for line in lines[-max(1, min(limit, 500)) :]:
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


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


class EvalCase(BaseModel):
    question: str = Field(..., min_length=1, max_length=1000)
    expected_keywords: list[str] = Field(default_factory=list)


class EvalRequest(BaseModel):
    cases: list[EvalCase] = Field(default_factory=list)
    include_diagnostics: bool = False


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


@router.get("/projects/{project_id}/documents")
async def list_project_documents(project_id: str) -> list[dict[str, Any]]:
    project = project_store.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    docs_dir = project_store.get_project_paths(project_id)["documents_dir"]
    docs_dir.mkdir(parents=True, exist_ok=True)

    output: list[dict[str, Any]] = []
    for p in docs_dir.iterdir():
        if p.is_file():
            stat = p.stat()
            output.append(
                {
                    "filename": p.name,
                    "size_bytes": stat.st_size,
                    "updated_at": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
                }
            )
    output.sort(key=lambda d: d["updated_at"], reverse=True)
    return output


@router.get("/projects/{project_id}/logs")
async def get_project_logs(project_id: str, limit: int = Query(default=50, ge=1, le=500)) -> list[dict[str, Any]]:
    project = project_store.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return _read_query_logs(project_id, limit=limit)


@router.post("/projects/{project_id}/reindex")
async def reindex_project(project_id: str) -> dict[str, Any]:
    project = project_store.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    try:
        from app.services.ingestion import IngestionService

        service = IngestionService()
        return await service.rebuild_project_index(project_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/projects/{project_id}/documents/{filename}")
async def delete_project_document(project_id: str, filename: str) -> dict[str, Any]:
    try:
        from app.services.ingestion import IngestionService

        service = IngestionService()
        return await service.delete_document(project_id, filename)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


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
        _append_query_log(
            project_id,
            {
                "question": request.question,
                "confidence": confidence,
                "abstained": abstained,
                "citations_count": len(citations),
                "diagnostics": diagnostics,
            },
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


@router.post("/projects/{project_id}/eval")
async def eval_project(project_id: str, request: EvalRequest) -> dict[str, Any]:
    project = project_store.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if not request.cases:
        return {
            "project_id": project_id,
            "total_cases": 0,
            "pass_rate": 0.0,
            "avg_confidence": 0.0,
            "results": [],
        }

    try:
        from app.services.rag import RAGService

        service = RAGService()
        results: list[dict[str, Any]] = []
        pass_count = 0
        confidence_sum = 0.0

        for case in request.cases:
            answer, citations, confidence, abstained, diagnostics = await service.query(
                case.question,
                project_id,
                include_diagnostics=request.include_diagnostics,
            )
            confidence_sum += confidence

            answer_lower = answer.lower()
            expected = [k.lower().strip() for k in case.expected_keywords if k.strip()]
            keyword_hits = [k for k in expected if k in answer_lower]
            case_pass = (len(keyword_hits) == len(expected)) and not abstained
            if case_pass:
                pass_count += 1

            results.append(
                {
                    "question": case.question,
                    "expected_keywords": case.expected_keywords,
                    "keyword_hits": keyword_hits,
                    "passed": case_pass,
                    "confidence": confidence,
                    "abstained": abstained,
                    "citations_count": len(citations),
                    "diagnostics": diagnostics if request.include_diagnostics else None,
                }
            )

        total = len(request.cases)
        pass_rate = round(pass_count / total, 4) if total else 0.0
        avg_confidence = round(confidence_sum / total, 4) if total else 0.0

        _append_query_log(
            project_id,
            {
                "type": "eval_run",
                "total_cases": total,
                "pass_rate": pass_rate,
                "avg_confidence": avg_confidence,
            },
        )

        return {
            "project_id": project_id,
            "total_cases": total,
            "pass_rate": pass_rate,
            "avg_confidence": avg_confidence,
            "results": results,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Backward-compatible endpoints mapped to default project
@router.post("/upload", response_model=UploadResponse)
async def upload_document(file: UploadFile = File(...)) -> UploadResponse:
    return await upload_document_to_project(settings.default_project_id, file)


@router.post("/query", response_model=QueryResponse)
async def query_documents(request: QueryRequest) -> QueryResponse:
    return await query_project_documents(settings.default_project_id, request)

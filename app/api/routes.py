"""
DocuChat RAG - API Routes

REST API endpoints for project-based document upload and querying.
"""

from __future__ import annotations

from typing import Any
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
import re

import fitz
from fastapi import APIRouter, File, HTTPException, UploadFile, Query, Request
from pydantic import BaseModel, Field

from app.config import get_settings
from app.services.projects import ProjectStore

router = APIRouter()
settings = get_settings()
project_store = ProjectStore()
project_store.ensure_default_project()
logger = logging.getLogger("docuchat.api.routes")


def _logs_path(project_id: str):
    return project_store.get_project_paths(project_id)["project_dir"] / "query_logs.jsonl"


def _audit_path(project_id: str):
    return project_store.get_project_paths(project_id)["project_dir"] / "audit_logs.jsonl"


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


def _append_audit_log(
    project_id: str,
    request: Request,
    action: str,
    status: str,
    details: dict[str, Any] | None = None,
) -> None:
    path = _audit_path(project_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "request_id": getattr(request.state, "request_id", None),
        "method": request.method,
        "path": request.url.path,
        "action": action,
        "status": status,
        "details": details or {},
    }
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload) + "\n")


def _eval_profiles_dir(project_id: str) -> Path:
    p = project_store.get_project_paths(project_id)["project_dir"] / "eval_profiles"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _save_eval_profile(project_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    profile_id = re.sub(r"[^a-zA-Z0-9_-]", "-", payload["profile_id"].strip())
    if not profile_id:
        raise ValueError("Invalid profile_id")
    payload["profile_id"] = profile_id
    payload["updated_at"] = datetime.now(timezone.utc).isoformat()
    path = _eval_profiles_dir(project_id) / f"{profile_id}.json"
    if not path.exists():
        payload["created_at"] = payload["updated_at"]
    else:
        existing = json.loads(path.read_text(encoding="utf-8"))
        payload["created_at"] = existing.get("created_at", payload["updated_at"])
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


def _list_eval_profiles(project_id: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for p in _eval_profiles_dir(project_id).glob("*.json"):
        try:
            out.append(json.loads(p.read_text(encoding="utf-8")))
        except Exception:
            continue
    out.sort(key=lambda x: x.get("updated_at", ""), reverse=True)
    return out


def _get_eval_profile(project_id: str, profile_id: str) -> dict[str, Any] | None:
    path = _eval_profiles_dir(project_id) / f"{profile_id}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _eval_datasets_dir(project_id: str) -> Path:
    p = project_store.get_project_paths(project_id)["project_dir"] / "eval_datasets"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _save_eval_dataset(project_id: str, dataset_id: str, cases: list[dict[str, Any]], profile_id: str | None = None) -> dict[str, Any]:
    safe_id = re.sub(r"[^a-zA-Z0-9_-]", "-", dataset_id.strip())
    if not safe_id:
        raise ValueError("Invalid dataset_id")
    payload = {
        "dataset_id": safe_id,
        "project_id": project_id,
        "profile_id": profile_id,
        "cases": cases,
        "count": len(cases),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    path = _eval_datasets_dir(project_id) / f"{safe_id}.json"
    if path.exists():
        existing = json.loads(path.read_text(encoding="utf-8"))
        payload["created_at"] = existing.get("created_at", payload["updated_at"])
    else:
        payload["created_at"] = payload["updated_at"]
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


def _get_eval_dataset(project_id: str, dataset_id: str) -> dict[str, Any] | None:
    path = _eval_datasets_dir(project_id) / f"{dataset_id}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _list_eval_datasets(project_id: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for p in _eval_datasets_dir(project_id).glob("*.json"):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            out.append({
                "dataset_id": data.get("dataset_id"),
                "count": data.get("count", 0),
                "profile_id": data.get("profile_id"),
                "updated_at": data.get("updated_at"),
            })
        except Exception:
            continue
    out.sort(key=lambda x: x.get("updated_at", ""), reverse=True)
    return out


def _sanitize_filename(filename: str) -> str:
    base = Path(filename).name.strip()
    if not base or base in {".", ".."}:
        raise ValueError("Invalid filename")
    return base


def _validate_upload(filename: str, size_bytes: int) -> str | None:
    allowed_types = {".pdf", ".txt"}
    file_ext = "." + filename.split(".")[-1].lower() if "." in filename else ""
    if file_ext not in allowed_types:
        return f"Unsupported file type. Allowed: {', '.join(sorted(allowed_types))}"
    if size_bytes > settings.max_file_size_bytes:
        return f"File too large. Maximum size: {settings.max_file_size_mb}MB"
    return None


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


class BatchUploadItem(BaseModel):
    filename: str
    success: bool
    document_id: str | None = None
    error: str | None = None


class BatchUploadResponse(BaseModel):
    project_id: str
    total_files: int
    succeeded: int
    failed: int
    results: list[BatchUploadItem]


class HealthResponse(BaseModel):
    status: str
    version: str


class EvalCase(BaseModel):
    question: str = Field(..., min_length=1, max_length=1000)
    expected_keywords: list[str] = Field(default_factory=list)


class EvalRequest(BaseModel):
    cases: list[EvalCase] = Field(default_factory=list)
    include_diagnostics: bool = False
    profile_id: str | None = None
    dataset_id: str | None = None


class EvalProfileRequest(BaseModel):
    profile_id: str = Field(..., min_length=2, max_length=64)
    name: str = Field(..., min_length=2, max_length=120)
    chatbot_type: str = Field(default="general", max_length=40)
    min_pass_rate: float = Field(default=0.7, ge=0.0, le=1.0)
    min_confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    require_citations: bool = True
    strict_abstain: bool = False


class EvalBootstrapRequest(BaseModel):
    profile_id: str | None = None
    max_cases: int = Field(default=30, ge=5, le=100)


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    return HealthResponse(status="healthy", version=settings.app_version)


@router.post("/projects")
async def create_project(request: ProjectCreateRequest, http_request: Request) -> dict[str, Any]:
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
        _append_audit_log(project["id"], http_request, "project.create", "success", {"name": project["name"]})
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
async def update_project(project_id: str, request: ProjectUpdateRequest, http_request: Request) -> dict[str, Any]:
    try:
        patch = request.model_dump(exclude_none=True)
        project = project_store.update_project(project_id, patch)
        _append_audit_log(project_id, http_request, "project.update", "success", {"fields": list(patch.keys())})
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


@router.get("/projects/{project_id}/audit")
async def get_project_audit_logs(project_id: str, limit: int = Query(default=50, ge=1, le=500)) -> list[dict[str, Any]]:
    project = project_store.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    path = _audit_path(project_id)
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


@router.get("/projects/{project_id}/ingestion/status")
async def get_ingestion_status(project_id: str) -> dict[str, Any]:
    project = project_store.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    docs = await list_project_documents(project_id)
    logs = _read_query_logs(project_id, limit=200)
    batch_logs = [l for l in logs if l.get("type") == "batch_upload"]
    last_batch = batch_logs[-1] if batch_logs else None

    return {
        "project_id": project_id,
        "documents_count": len(docs),
        "last_batch_upload": last_batch,
        "recent_batch_uploads": batch_logs[-5:],
    }


@router.post("/projects/{project_id}/reindex")
async def reindex_project(project_id: str, http_request: Request) -> dict[str, Any]:
    project = project_store.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    try:
        from app.services.ingestion import IngestionService

        service = IngestionService()
        result = await service.rebuild_project_index(project_id)
        _append_audit_log(project_id, http_request, "project.reindex", "success", result)
        return result
    except Exception:
        logger.exception("Failed to reindex project", extra={"project_id": project_id})
        _append_audit_log(project_id, http_request, "project.reindex", "error")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/projects/{project_id}/documents/{filename}")
async def delete_project_document(project_id: str, filename: str, http_request: Request) -> dict[str, Any]:
    try:
        safe_filename = _sanitize_filename(filename)
        from app.services.ingestion import IngestionService

        service = IngestionService()
        result = await service.delete_document(project_id, safe_filename)
        _append_audit_log(project_id, http_request, "document.delete", "success", {"filename": safe_filename})
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception:
        logger.exception("Failed to delete document", extra={"project_id": project_id, "file_name": safe_filename})
        _append_audit_log(project_id, http_request, "document.delete", "error", {"filename": safe_filename})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/projects/{project_id}/upload", response_model=UploadResponse)
async def upload_document_to_project(project_id: str, file: UploadFile = File(...), http_request: Request = None) -> UploadResponse:
    raw_filename = file.filename or "unknown"
    try:
        filename = _sanitize_filename(raw_filename)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    contents = await file.read()

    validation_error = _validate_upload(filename, len(contents))
    if validation_error:
        raise HTTPException(status_code=400, detail=validation_error)

    try:
        from app.services.ingestion import IngestionService

        service = IngestionService()
        document_id = await service.process_document(contents, filename, project_id)

        if http_request:
            _append_audit_log(project_id, http_request, "document.upload", "success", {"filename": filename})
        return UploadResponse(
            message="Document uploaded and indexed successfully",
            document_id=document_id,
            filename=filename,
            project_id=project_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception:
        logger.exception("Failed to upload document", extra={"project_id": project_id, "file_name": filename})
        if http_request:
            _append_audit_log(project_id, http_request, "document.upload", "error", {"filename": filename})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/projects/{project_id}/upload/batch", response_model=BatchUploadResponse)
async def batch_upload_documents(project_id: str, files: list[UploadFile] = File(...), http_request: Request = None) -> BatchUploadResponse:
    project = project_store.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if not files:
        raise HTTPException(status_code=400, detail="No files provided")

    from app.services.ingestion import IngestionService

    service = IngestionService()
    results: list[BatchUploadItem] = []

    for file in files:
        raw_filename = file.filename or "unknown"
        try:
            filename = _sanitize_filename(raw_filename)
        except ValueError as e:
            results.append(BatchUploadItem(filename=raw_filename, success=False, error=str(e)))
            continue

        contents = await file.read()

        validation_error = _validate_upload(filename, len(contents))
        if validation_error:
            results.append(BatchUploadItem(filename=filename, success=False, error=validation_error))
            continue

        try:
            document_id = await service.process_document(contents, filename, project_id)
            results.append(BatchUploadItem(filename=filename, success=True, document_id=document_id))
        except Exception:
            logger.exception("Failed batch upload item", extra={"project_id": project_id, "file_name": filename})
            results.append(BatchUploadItem(filename=filename, success=False, error="Internal server error"))

    succeeded = sum(1 for r in results if r.success)
    failed = len(results) - succeeded

    _append_query_log(
        project_id,
        {
            "type": "batch_upload",
            "total_files": len(results),
            "succeeded": succeeded,
            "failed": failed,
            "request_id": getattr(http_request.state, "request_id", None) if http_request else None,
        },
    )
    if http_request:
        _append_audit_log(
            project_id,
            http_request,
            "document.batch_upload",
            "success" if failed == 0 else "partial",
            {"total_files": len(results), "succeeded": succeeded, "failed": failed},
        )

    return BatchUploadResponse(
        project_id=project_id,
        total_files=len(results),
        succeeded=succeeded,
        failed=failed,
        results=results,
    )


@router.post("/projects/{project_id}/query", response_model=QueryResponse)
async def query_project_documents(project_id: str, request: QueryRequest, http_request: Request) -> QueryResponse:
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
                "request_id": getattr(http_request.state, "request_id", None),
            },
        )
        _append_audit_log(
            project_id,
            http_request,
            "query.run",
            "success",
            {"confidence": confidence, "abstained": abstained, "citations_count": len(citations)},
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
    except Exception:
        logger.exception("Failed project query", extra={"project_id": project_id})
        _append_audit_log(project_id, http_request, "query.run", "error")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/projects/{project_id}/eval/profiles")
async def upsert_eval_profile(project_id: str, request: EvalProfileRequest, http_request: Request) -> dict[str, Any]:
    project = project_store.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    try:
        payload = request.model_dump()
        saved = _save_eval_profile(project_id, payload)
        _append_audit_log(project_id, http_request, "eval.profile.upsert", "success", {"profile_id": saved["profile_id"]})
        return saved
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/projects/{project_id}/eval/profiles")
async def list_eval_profiles(project_id: str) -> list[dict[str, Any]]:
    project = project_store.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return _list_eval_profiles(project_id)


@router.get("/projects/{project_id}/eval/datasets")
async def list_eval_datasets(project_id: str) -> list[dict[str, Any]]:
    project = project_store.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return _list_eval_datasets(project_id)


@router.get("/projects/{project_id}/eval/datasets/{dataset_id}")
async def get_eval_dataset(project_id: str, dataset_id: str) -> dict[str, Any]:
    project = project_store.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    dataset = _get_eval_dataset(project_id, dataset_id)
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")
    return dataset


@router.post("/projects/{project_id}/eval/bootstrap")
async def bootstrap_eval_dataset(project_id: str, request: EvalBootstrapRequest, http_request: Request) -> dict[str, Any]:
    project = project_store.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    docs_dir = project_store.get_project_paths(project_id)["documents_dir"]
    docs_dir.mkdir(parents=True, exist_ok=True)

    cases: list[dict[str, Any]] = []
    for p in sorted(docs_dir.iterdir()):
        if not p.is_file():
            continue
        # universal basic cases
        cases.append({"question": f"What are the key points in {p.name}?", "expected_keywords": []})
        cases.append({"question": f"Summarize {p.name} in plain language.", "expected_keywords": []})

        # lightweight keyword extraction from text/PDF snippet
        try:
            snippet = ""
            if p.suffix.lower() == ".txt":
                snippet = p.read_text(encoding="utf-8", errors="ignore")[:2500]
            elif p.suffix.lower() == ".pdf":
                with fitz.open(p) as pdf:
                    if len(pdf) > 0:
                        snippet = pdf[0].get_text()[:2500]

            words = [w.lower() for w in re.findall(r"[a-zA-Z]{5,}", snippet)]
            freq: dict[str, int] = {}
            for w in words:
                freq[w] = freq.get(w, 0) + 1
            top = [k for k, _ in sorted(freq.items(), key=lambda kv: kv[1], reverse=True)[:3]]
            if top:
                cases.append({"question": f"What does {p.name} say about {top[0]}?", "expected_keywords": top[:2]})
        except Exception:
            continue

    # add out-of-scope safety checks
    cases.append({"question": "What is the office Wi-Fi password?", "expected_keywords": []})
    cases.append({"question": "Tell me information not present in these documents.", "expected_keywords": []})

    max_cases = min(request.max_cases, len(cases))
    cases = cases[:max_cases]

    dataset_id = f"bootstrap-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"
    saved = _save_eval_dataset(project_id, dataset_id, cases, profile_id=request.profile_id)

    _append_audit_log(project_id, http_request, "eval.bootstrap", "success", {"cases": len(cases), "dataset_id": dataset_id})
    return {
        "project_id": project_id,
        "profile_id": request.profile_id,
        "dataset_id": dataset_id,
        "cases_generated": len(cases),
        "cases": cases,
        "saved": {"dataset_id": saved["dataset_id"], "count": saved["count"]},
    }


@router.post("/projects/{project_id}/eval")
async def eval_project(project_id: str, request: EvalRequest, http_request: Request) -> dict[str, Any]:
    project = project_store.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    profile = _get_eval_profile(project_id, request.profile_id) if request.profile_id else None
    if request.profile_id and not profile:
        raise HTTPException(status_code=404, detail="Eval profile not found")

    run_cases = list(request.cases)
    if request.dataset_id:
        dataset = _get_eval_dataset(project_id, request.dataset_id)
        if not dataset:
            raise HTTPException(status_code=404, detail="Eval dataset not found")
        run_cases = [EvalCase(**c) for c in dataset.get("cases", [])]

    if not run_cases:
        return {
            "project_id": project_id,
            "profile_id": request.profile_id,
            "dataset_id": request.dataset_id,
            "total_cases": 0,
            "pass_rate": 0.0,
            "avg_confidence": 0.0,
            "meets_profile_thresholds": None,
            "results": [],
        }

    try:
        from app.services.rag import RAGService

        service = RAGService()
        results: list[dict[str, Any]] = []
        pass_count = 0
        confidence_sum = 0.0

        for case in run_cases:
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

        total = len(run_cases)
        pass_rate = round(pass_count / total, 4) if total else 0.0
        avg_confidence = round(confidence_sum / total, 4) if total else 0.0

        meets_profile_thresholds = None
        if profile:
            min_pass_rate = float(profile.get("min_pass_rate", 0.7))
            min_confidence = float(profile.get("min_confidence", 0.5))
            require_citations = bool(profile.get("require_citations", True))
            strict_abstain = bool(profile.get("strict_abstain", False))

            citation_ok = True
            abstain_ok = True
            if require_citations:
                citation_ok = all((r.get("citations_count", 0) > 0) for r in results)
            if strict_abstain:
                abstain_ok = all((not r.get("abstained", False)) for r in results)

            meets_profile_thresholds = (
                pass_rate >= min_pass_rate
                and avg_confidence >= min_confidence
                and citation_ok
                and abstain_ok
            )

        _append_query_log(
            project_id,
            {
                "type": "eval_run",
                "total_cases": total,
                "pass_rate": pass_rate,
                "avg_confidence": avg_confidence,
                "profile_id": request.profile_id,
                "dataset_id": request.dataset_id,
                "meets_profile_thresholds": meets_profile_thresholds,
                "request_id": getattr(http_request.state, "request_id", None),
            },
        )
        _append_audit_log(
            project_id,
            http_request,
            "eval.run",
            "success",
            {"total_cases": total, "pass_rate": pass_rate, "avg_confidence": avg_confidence},
        )

        return {
            "project_id": project_id,
            "profile_id": request.profile_id,
            "dataset_id": request.dataset_id,
            "total_cases": total,
            "pass_rate": pass_rate,
            "avg_confidence": avg_confidence,
            "meets_profile_thresholds": meets_profile_thresholds,
            "profile_thresholds": {
                "min_pass_rate": profile.get("min_pass_rate") if profile else None,
                "min_confidence": profile.get("min_confidence") if profile else None,
                "require_citations": profile.get("require_citations") if profile else None,
                "strict_abstain": profile.get("strict_abstain") if profile else None,
            },
            "results": results,
        }
    except Exception:
        logger.exception("Failed eval run", extra={"project_id": project_id})
        _append_audit_log(project_id, http_request, "eval.run", "error")
        raise HTTPException(status_code=500, detail="Internal server error")


# Backward-compatible endpoints mapped to default project
@router.post("/upload", response_model=UploadResponse)
async def upload_document(file: UploadFile = File(...), http_request: Request = None) -> UploadResponse:
    return await upload_document_to_project(settings.default_project_id, file, http_request)


@router.post("/query", response_model=QueryResponse)
async def query_documents(request: QueryRequest, http_request: Request) -> QueryResponse:
    return await query_project_documents(settings.default_project_id, request, http_request)

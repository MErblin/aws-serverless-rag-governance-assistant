"""
Project configuration and storage helpers.

Provides lightweight project isolation for prompts/settings/index storage.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.config import get_settings

settings = get_settings()


class ProjectStore:
    """Filesystem-backed project registry."""

    def __init__(self) -> None:
        self.projects_root = settings.projects_root_path
        self.projects_root.mkdir(parents=True, exist_ok=True)

    def _project_dir(self, project_id: str) -> Path:
        return self.projects_root / project_id

    def _config_path(self, project_id: str) -> Path:
        return self._project_dir(project_id) / "config.json"

    def ensure_default_project(self) -> dict[str, Any]:
        default_id = settings.default_project_id
        existing = self.get_project(default_id)
        if existing:
            return existing

        return self.create_project(
            name="Default DocChat",
            description="Default project",
            project_id=default_id,
            system_prompt=settings.default_system_prompt,
            model=settings.ollama_model,
            top_k=3,
            chunk_size=settings.chunk_size,
            chunk_overlap=settings.chunk_overlap,
        )

    def create_project(
        self,
        name: str,
        description: str | None = None,
        project_id: str | None = None,
        system_prompt: str | None = None,
        model: str | None = None,
        top_k: int = 3,
        chunk_size: int | None = None,
        chunk_overlap: int | None = None,
    ) -> dict[str, Any]:
        project_id = project_id or self._slug(name)
        project_dir = self._project_dir(project_id)
        if project_dir.exists():
            raise ValueError(f"Project already exists: {project_id}")

        now = datetime.now(timezone.utc).isoformat()
        project_dir.mkdir(parents=True, exist_ok=False)
        (project_dir / "index").mkdir(parents=True, exist_ok=True)
        (project_dir / "documents").mkdir(parents=True, exist_ok=True)

        payload = {
            "id": project_id,
            "name": name,
            "description": description or "",
            "system_prompt": system_prompt or settings.default_system_prompt,
            "model": model or settings.ollama_model,
            "top_k": top_k,
            "chunk_size": chunk_size or settings.chunk_size,
            "chunk_overlap": chunk_overlap or settings.chunk_overlap,
            "created_at": now,
            "updated_at": now,
        }

        self._write_json(self._config_path(project_id), payload)
        return payload

    def list_projects(self) -> list[dict[str, Any]]:
        projects: list[dict[str, Any]] = []
        for child in self.projects_root.iterdir():
            if child.is_dir() and (child / "config.json").exists():
                projects.append(self._read_json(child / "config.json"))
        projects.sort(key=lambda p: p.get("updated_at", ""), reverse=True)
        return projects

    def get_project(self, project_id: str) -> dict[str, Any] | None:
        path = self._config_path(project_id)
        if not path.exists():
            return None
        return self._read_json(path)

    def update_project(self, project_id: str, patch: dict[str, Any]) -> dict[str, Any]:
        project = self.get_project(project_id)
        if not project:
            raise ValueError("Project not found")

        allowed = {
            "name",
            "description",
            "system_prompt",
            "model",
            "top_k",
            "chunk_size",
            "chunk_overlap",
        }
        for key, value in patch.items():
            if key in allowed and value is not None:
                project[key] = value

        project["updated_at"] = datetime.now(timezone.utc).isoformat()
        self._write_json(self._config_path(project_id), project)
        return project

    def get_project_paths(self, project_id: str) -> dict[str, Path]:
        project_dir = self._project_dir(project_id)
        return {
            "project_dir": project_dir,
            "index_dir": project_dir / "index",
            "documents_dir": project_dir / "documents",
            "config_path": self._config_path(project_id),
        }

    def _slug(self, name: str) -> str:
        slug = "".join(ch.lower() if ch.isalnum() else "-" for ch in name).strip("-")
        slug = "-".join(part for part in slug.split("-") if part)
        return slug[:64] if slug else f"project-{uuid4().hex[:8]}"

    def _read_json(self, path: Path) -> dict[str, Any]:
        return json.loads(path.read_text(encoding="utf-8"))

    def _write_json(self, path: Path, payload: dict[str, Any]) -> None:
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

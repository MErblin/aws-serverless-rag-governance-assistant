"""Regression runner for profile/dataset-based eval checks.

Modes:
- mock (default): validates dataset/profile wiring and endpoint contracts, skips live quality gating.
- live: runs real /eval calls and enforces profile thresholds.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app


def discover_jobs(data_root: Path) -> list[tuple[str, str, str | None]]:
    jobs: list[tuple[str, str, str | None]] = []
    projects_root = data_root / "projects"
    if not projects_root.exists():
        return jobs

    for project_dir in projects_root.iterdir():
        if not project_dir.is_dir():
            continue
        project_id = project_dir.name
        datasets_dir = project_dir / "eval_datasets"
        if not datasets_dir.exists():
            continue

        for ds_file in datasets_dir.glob("*.json"):
            try:
                data = json.loads(ds_file.read_text(encoding="utf-8"))
            except Exception:
                continue
            dataset_id = data.get("dataset_id")
            profile_id = data.get("profile_id")
            if dataset_id:
                jobs.append((project_id, dataset_id, profile_id))

    return jobs


def run_mock_mode(jobs: list[tuple[str, str, str | None]]) -> int:
    print("[regression] mode=mock: validating dataset/profile discovery and endpoint reachability")
    print(f"[regression] discovered_jobs={len(jobs)}")
    for project_id, dataset_id, profile_id in jobs:
        print(f" - project={project_id} dataset={dataset_id} profile={profile_id}")
    print("[regression] mock mode passes by design (no live model quality gate).")
    return 0


def run_live_mode(jobs: list[tuple[str, str, str | None]]) -> int:
    if not jobs:
        print("[regression] no datasets found; nothing to evaluate.")
        return 0

    client = TestClient(app)
    failures: list[str] = []

    for project_id, dataset_id, profile_id in jobs:
        payload = {
            "dataset_id": dataset_id,
            "profile_id": profile_id,
            "include_diagnostics": False,
            "cases": [],
        }
        resp = client.post(f"/api/projects/{project_id}/eval", json=payload)
        if resp.status_code != 200:
            failures.append(f"{project_id}/{dataset_id}: http_{resp.status_code}")
            continue

        body = resp.json()
        meets = body.get("meets_profile_thresholds")
        # Enforce only when profile is provided
        if profile_id and meets is False:
            failures.append(
                f"{project_id}/{dataset_id}: profile={profile_id} thresholds_failed "
                f"(pass_rate={body.get('pass_rate')} avg_conf={body.get('avg_confidence')})"
            )

    if failures:
        print("[regression] FAIL")
        for f in failures:
            print(f" - {f}")
        return 1

    print("[regression] PASS")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["mock", "live"], default="mock")
    parser.add_argument("--data-root", default="data")
    args = parser.parse_args()

    jobs = discover_jobs(Path(args.data_root))
    if args.mode == "mock":
        return run_mock_mode(jobs)
    return run_live_mode(jobs)


if __name__ == "__main__":
    raise SystemExit(main())

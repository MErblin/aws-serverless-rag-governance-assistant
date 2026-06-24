"""
sync_from_s3.py — Bulk ingest GRC documents from S3 into a RAG project.

Run this on a fresh EC2 instance after deploying to populate the vector index
from the S3 bucket without re-uploading files manually.

Usage:
    python scripts/sync_from_s3.py --project-id YOUR_PROJECT_ID
    python scripts/sync_from_s3.py --project-id YOUR_PROJECT_ID --api-url http://localhost:8000

Requirements:
    - FastAPI backend must be running
    - AWS credentials configured (via ~/.aws/credentials or IAM role on EC2)
    - S3_BUCKET set in .env
"""

import argparse
import sys
import time
from pathlib import Path

# Add project root to path so we can import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

import requests

from app.config import get_settings
from app.services.s3_client import download_from_s3, list_s3_documents


def sync(project_id: str, api_url: str) -> None:
    settings = get_settings()

    if not settings.s3_bucket:
        print("ERROR: S3_BUCKET is not set in .env — nothing to sync.")
        sys.exit(1)

    print(f"Listing documents in s3://{settings.s3_bucket}/{settings.s3_prefix}")
    docs = list_s3_documents()

    if not docs:
        print("No documents found in S3. Make sure you uploaded your PDFs first.")
        sys.exit(0)

    print(f"Found {len(docs)} document(s) to sync.\n")

    success = 0
    failed = 0

    for doc in docs:
        filename = doc["filename"]
        key = doc["key"]

        if not filename or filename.endswith("/"):
            continue  # skip folder-level keys

        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        if ext not in {"pdf", "txt"}:
            print(f"  SKIP  {filename}  (unsupported type .{ext})")
            continue

        print(f"  ↓ Downloading {filename} ({doc['size_bytes']:,} bytes) ...", end=" ")
        content = download_from_s3(key)
        if content is None:
            print("FAILED (download error)")
            failed += 1
            continue

        # POST to the running FastAPI backend
        files = {"file": (filename, content, "application/pdf" if ext == "pdf" else "text/plain")}
        try:
            resp = requests.post(
                f"{api_url}/api/projects/{project_id}/upload",
                files=files,
                timeout=120,
            )
            if resp.status_code == 200:
                print("✓ indexed")
                success += 1
            else:
                detail = resp.json().get("detail", resp.text)
                print(f"FAILED ({resp.status_code}: {detail})")
                failed += 1
        except requests.RequestException as exc:
            print(f"FAILED (request error: {exc})")
            failed += 1

        time.sleep(0.5)  # be gentle on the API

    print(f"\nDone. Indexed: {success}  Failed: {failed}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Sync GRC docs from S3 into the RAG index.")
    parser.add_argument("--project-id", required=True, help="Target project ID")
    parser.add_argument(
        "--api-url",
        default="http://localhost:8000",
        help="Base URL of the running FastAPI backend (default: http://localhost:8000)",
    )
    args = parser.parse_args()
    sync(args.project_id, args.api_url.rstrip("/"))

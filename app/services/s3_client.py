"""
DocuChat RAG - S3 Client

Thin wrapper around boto3 for uploading and downloading
GRC documents from an S3 bucket.

S3_BUCKET must be set in .env. If empty, all S3 operations are no-ops.
"""

import logging
from typing import Optional

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from app.config import get_settings

logger = logging.getLogger("docuchat.api.s3")


def _get_client():
    settings = get_settings()
    return boto3.client("s3", region_name=settings.aws_region)


def upload_to_s3(filename: str, content: bytes) -> Optional[str]:
    """
    Upload document bytes to S3.

    Args:
        filename: The filename (no path) to use as the S3 object name.
        content: Raw file bytes.

    Returns:
        The S3 key if successful, None if S3 is not configured.
    """
    settings = get_settings()
    if not settings.s3_bucket:
        return None

    key = f"{settings.s3_prefix.rstrip('/')}/{filename}"
    try:
        _get_client().put_object(
            Bucket=settings.s3_bucket,
            Key=key,
            Body=content,
            ContentType="application/pdf" if filename.endswith(".pdf") else "text/plain",
        )
        logger.info("Uploaded to S3: s3://%s/%s", settings.s3_bucket, key)
        return key
    except (BotoCoreError, ClientError) as exc:
        logger.error("S3 upload failed for %s: %s", filename, exc)
        return None


def list_s3_documents() -> list[dict]:
    """
    List all documents in the configured S3 bucket/prefix.

    Returns:
        List of dicts with 'key', 'filename', and 'size_bytes'.
    """
    settings = get_settings()
    if not settings.s3_bucket:
        return []

    try:
        response = _get_client().list_objects_v2(
            Bucket=settings.s3_bucket,
            Prefix=settings.s3_prefix,
        )
        items = []
        for obj in response.get("Contents", []):
            key = obj["Key"]
            items.append({
                "key": key,
                "filename": key.split("/")[-1],
                "size_bytes": obj["Size"],
            })
        return items
    except (BotoCoreError, ClientError) as exc:
        logger.error("S3 list failed: %s", exc)
        return []


def download_from_s3(key: str) -> Optional[bytes]:
    """
    Download a document from S3 by its full key.

    Args:
        key: Full S3 object key (e.g. 'grc-docs/NIST.SP.800-37r2.pdf').

    Returns:
        File bytes, or None on failure.
    """
    settings = get_settings()
    if not settings.s3_bucket:
        return None

    try:
        response = _get_client().get_object(Bucket=settings.s3_bucket, Key=key)
        return response["Body"].read()
    except (BotoCoreError, ClientError) as exc:
        logger.error("S3 download failed for %s: %s", key, exc)
        return None

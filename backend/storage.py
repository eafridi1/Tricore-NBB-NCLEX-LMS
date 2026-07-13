"""
storage.py — Abstraction layer over file storage.
Week 3: returns fake signed URLs for local dev.
Week 5+: swap _generate_signed_url() to call Cloudflare R2 via boto3.
"""
import os
from datetime import datetime, timedelta, timezone

STORAGE_BASE = os.getenv("STORAGE_BASE_URL", "http://localhost:8000/static")
R2_CONFIGURED = bool(os.getenv("R2_ACCESS_KEY"))

def get_signed_url(object_key: str, expires_in_seconds: int = 3600) -> str:
    if R2_CONFIGURED:
        # Week 5: real R2 presigned URL
        # import boto3
        # s3 = boto3.client('s3', endpoint_url=os.getenv("R2_ENDPOINT"), ...)
        # return s3.generate_presigned_url(...)
        raise NotImplementedError("R2 not configured yet")
    # Local dev: return a fake URL that makes the shape correct
    expires = int((datetime.now(timezone.utc) + timedelta(seconds=expires_in_seconds)).timestamp())
    return f"{STORAGE_BASE}/{object_key}?expires={expires}&dev=true"

def get_storage_url_for_upload(filename: str) -> tuple[str, str]:
    """Returns (object_key, upload_url). Week 3: fake. Week 5: real presigned PUT."""
    object_key = f"uploads/{filename}"
    return object_key, f"{STORAGE_BASE}/{object_key}"
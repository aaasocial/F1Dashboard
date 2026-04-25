"""POST /sessions/upload — API-06, D-07, D-08."""
from __future__ import annotations

import logging
import shutil

from fastapi import APIRouter, File, HTTPException, UploadFile

from f1_api.schemas.sessions import SessionUploadResponse
from f1_api.services.sessions import (
    MAX_UPLOAD_BYTES,
    compute_expires_at,
    extract_session_zip,
    register_session_upload,
)

log = logging.getLogger(__name__)
router = APIRouter()


@router.post("/sessions/upload", response_model=SessionUploadResponse)
def upload_session(file: UploadFile = File(...)) -> SessionUploadResponse:
    """Accept a zip of a FastF1 cache directory (D-08) with 1-hour TTL (D-07).

    Security: calls extract_session_zip which enforces Zip Slip, decompression
    bomb, symlink, and size caps (T-4-ZIP, T-4-BOMB, T-4-SYMLINK).
    """
    # MIME-type guard (lightweight; real security is in extract_session_zip)
    if file.content_type not in (
        "application/zip",
        "application/x-zip-compressed",
        "application/octet-stream",
    ):
        raise HTTPException(
            status_code=415,
            detail=f"expected zip upload, got content_type={file.content_type!r}",
        )

    zip_bytes = file.file.read(MAX_UPLOAD_BYTES + 1)
    if len(zip_bytes) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"upload exceeds {MAX_UPLOAD_BYTES} byte limit",
        )
    session_id, session_dir = register_session_upload()
    try:
        extract_session_zip(zip_bytes, session_dir)
    except ValueError as e:
        # Rollback: remove the partially-created session dir
        shutil.rmtree(session_dir, ignore_errors=True)
        raise HTTPException(status_code=400, detail=str(e)) from e

    return SessionUploadResponse(
        session_id=session_id,
        expires_at=compute_expires_at(),
    )

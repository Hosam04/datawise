"""Serve stored profile-picture files at their /profiles/... reference path.

The files live under ``Config.STORAGE_PATH/profiles`` and are referenced from
``users.picture`` (e.g. ``/profiles/<user_id>_<nonce>.jpg``).  Only filenames
matching the exact pattern the uploader produces are served — anything else
(including path traversal attempts) returns 404.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from backend.core.config import Config

router = APIRouter(prefix="/profiles", tags=["Profiles"])

_PICTURE_PATH_RE = re.compile(r"^[0-9a-f-]{36}_[0-9]{13}\.(jpg|png)$")


@router.get("/{filename}")
def get_profile_picture(filename: str):
    """Return a stored profile picture (public, no auth required)."""
    if not _PICTURE_PATH_RE.match(filename):
        raise HTTPException(status_code=404, detail="Not found")

    profiles_dir = (Path(Config.STORAGE_PATH) / "profiles").resolve()
    target = (profiles_dir / filename).resolve()

    # Defence in depth: the target must stay inside the profiles directory.
    if profiles_dir != target.parent or not target.is_file():
        raise HTTPException(status_code=404, detail="Not found")

    media_type = "image/png" if filename.endswith(".png") else "image/jpeg"
    return FileResponse(target, media_type=media_type)
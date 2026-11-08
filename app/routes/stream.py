"""Streaming audio avec support Range."""
from __future__ import annotations

import mimetypes
import os
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, Response

from ..database import conn_ctx

router = APIRouter()


@router.get("/stream/{track_id}")
def stream_track(track_id: int, request: Request):
    with conn_ctx() as c:
        row = c.execute("SELECT path FROM tracks WHERE id=?", (track_id,)).fetchone()
    if not row:
        return Response(status_code=404)
    path = Path(row["path"])
    if not path.is_file():
        return Response(status_code=404)
    size = path.stat().st_size
    mime = mimetypes.guess_type(str(path))[0] or "audio/mpeg"

    range_header = request.headers.get("range")
    if not range_header:
        return FileResponse(path, media_type=mime, headers={"Accept-Ranges": "bytes"})

    # parse Range: bytes=start-end
    try:
        units, rng = range_header.split("=", 1)
        if units.strip().lower() != "bytes":
            raise ValueError
        start_str, end_str = rng.split("-", 1)
        start = int(start_str) if start_str.strip() else 0
        end = int(end_str) if end_str.strip() else size - 1
    except Exception:
        return Response(status_code=416, headers={"Content-Range": f"bytes */{size}"})

    if start >= size or end >= size or start > end:
        return Response(status_code=416, headers={"Content-Range": f"bytes */{size}"})

    length = end - start + 1
    with open(path, "rb") as f:
        f.seek(start)
        data = f.read(length)

    headers = {
        "Content-Range": f"bytes {start}-{end}/{size}",
        "Accept-Ranges": "bytes",
        "Content-Length": str(length),
    }
    return Response(content=data, status_code=206, media_type=mime, headers=headers)
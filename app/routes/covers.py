"""Routes pochettes : recherche, application, upload."""
from __future__ import annotations

import shutil
from pathlib import Path

from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from pathlib import Path

from ..config import get_config
from ..database import conn_ctx
from ..services.covers import download_cover, search_cover

router = APIRouter()


@router.get("/api/tracks/{track_id}/covers")
def search_covers(track_id: int):
    with conn_ctx() as c:
        row = c.execute("SELECT artist, title FROM tracks WHERE id=?", (track_id,)).fetchone()
    if not row:
        return JSONResponse({"error": "not found"}, status_code=404)
    res = search_cover(row["artist"], row["title"])
    return JSONResponse({"results": res})


@router.get("/cover/{track_id}")
def get_cover(track_id: int):
    with conn_ctx() as c:
        row = c.execute("SELECT cover_path FROM tracks WHERE id=?", (track_id,)).fetchone()
    if not row or not row["cover_path"]:
        return FileResponse("app/static/img/placeholder.svg", media_type="image/svg+xml")
    p = Path(row["cover_path"])
    if not p.is_file():
        return FileResponse("app/static/img/placeholder.svg", media_type="image/svg+xml")
    return FileResponse(p)


@router.post("/api/tracks/{track_id}/cover")
def apply_cover(track_id: int, image_url: str = Form(None), file: UploadFile = File(None)):
    cfg = get_config()
    cover_path = None
    if file is not None and file.filename:
        cover_dir = cfg.media_dir / ".covers"
        cover_dir.mkdir(exist_ok=True)
        dest = cover_dir / f"track_{track_id}_custom.jpg"
        with open(dest, "wb") as f:
            shutil.copyfileobj(file.file, f)
        cover_path = str(dest.resolve())
    elif image_url:
        cover_path = download_cover(image_url, track_id)
    if cover_path is None:
        return JSONResponse({"error": "failed"}, status_code=400)
    with conn_ctx() as c:
        c.execute("UPDATE tracks SET cover_path=? WHERE id=?", (cover_path, track_id))
    return JSONResponse({"ok": True, "cover_path": cover_path})
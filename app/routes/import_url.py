"""Import par URL avec progression (jobs)."""
from __future__ import annotations

import asyncio

from fastapi import APIRouter, BackgroundTasks, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse

from .. import templates
from ..services.importer import create_job, get_job, run_import

router = APIRouter()


@router.get("/import", response_class=HTMLResponse)
def import_page(request: Request):
    from ..plugins.loader import import_tabs
    return templates.TemplateResponse(request, "import.html", {"import_tabs": import_tabs()})


@router.get("/api/import/plugin-tabs")
def plugin_import_tabs():
    from ..plugins.loader import import_tabs
    return JSONResponse(import_tabs())


@router.post("/api/import/files")
async def import_files(files: list[UploadFile] = File(...)):
    from ..config import get_config
    from ..services.scanner import index_file
    cfg = get_config()
    results = []
    for f in files:
        if not f.filename:
            continue
        dest = cfg.media_dir / f.filename
        i = 1
        base = dest.stem
        while dest.exists():
            dest = cfg.media_dir / f"{base}_{i}.mp3"
            i += 1
        content = await f.read()
        dest.write_bytes(content)
        tid = index_file(dest)
        results.append({"filename": f.filename, "track_id": tid})
    return JSONResponse({"results": results})


@router.post("/api/import/url")
async def start_import(url: str = Form(...), background_tasks: BackgroundTasks = None):
    from ..services.audio_source import validate_url
    ok, msg = validate_url(url)
    if not ok:
        return JSONResponse({"error": msg}, status_code=400)
    jid = create_job(url)
    background_tasks.add_task(run_import, jid)
    return JSONResponse({"job_id": jid})


@router.get("/api/import/status/{job_id}")
async def import_status(job_id: str):
    job = get_job(job_id)
    if not job:
        return JSONResponse({"error": "unknown job"}, status_code=404)
    return JSONResponse(job)
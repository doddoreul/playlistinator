"""Import par URL avec progression (jobs)."""
from __future__ import annotations

import asyncio

from fastapi import APIRouter, BackgroundTasks, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse

from .. import templates
from ..services.importer import create_job, get_job, run_import

router = APIRouter()


@router.get("/import", response_class=HTMLResponse)
def import_page(request: Request):
    from ..plugins.loader import import_tabs
    return templates.TemplateResponse(request, "import.html", {"import_tabs": import_tabs()})


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
        return JSONResponse({"error": "job inconnu"}, status_code=404)
    return JSONResponse(job)
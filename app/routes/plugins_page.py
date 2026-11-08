"""Page de gestion des plugins."""
from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse

from .. import templates
from ..plugins.loader import discover_plugins, activate_plugin, deactivate_plugin

router = APIRouter()


@router.get("/plugins", response_class=HTMLResponse)
def plugins_page(request: Request):
    return templates.TemplateResponse(request, "plugins_page.html", {
        "plugins": discover_plugins(),
    })


@router.post("/api/plugins/{name}/activate")
def api_activate(name: str):
    ok, msg = activate_plugin(name)
    status = 200 if ok else 400
    return JSONResponse({"ok": ok, "message": msg}, status_code=status)


@router.post("/api/plugins/{name}/deactivate")
def api_deactivate(name: str):
    ok, msg = deactivate_plugin(name)
    status = 200 if ok else 400
    return JSONResponse({"ok": ok, "message": msg}, status_code=status)
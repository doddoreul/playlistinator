"""Routes bibliothèque : liste, recherche, scan, édition, suppression."""
from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse

from ..config import get_config
from ..database import conn_ctx
from ..models import Track
from ..services.metadata import build_metadata, write_tags
from ..services.scanner import scan_media
from .. import templates

log = logging.getLogger("playlistinator.library")
router = APIRouter()


def _tracks(q: str = "", artist: str = "", album: str = "") -> list[Track]:
    sql = "SELECT * FROM tracks WHERE 1=1"
    params = []
    if q:
        sql += " AND (title LIKE ? OR artist LIKE ?)"
        params += [f"%{q}%", f"%{q}%"]
    if artist:
        sql += " AND artist LIKE ?"
        params.append(f"%{artist}%")
    if album:
        sql += " AND album LIKE ?"
        params.append(f"%{album}%")
    sql += " ORDER BY artist, title"
    with conn_ctx() as c:
        rows = c.execute(sql, params).fetchall()
    return [Track.from_row(r) for r in rows]


@router.get("/", response_class=HTMLResponse)
def home(request: Request):
    tracks = _tracks()
    playlists = _list_playlists()
    return templates.TemplateResponse(request, "index.html", {
        "tracks": tracks, "playlists": playlists,
    })


@router.get("/api/tracks", response_class=HTMLResponse)
def tracks_partial(request: Request, q: str = "", artist: str = "", album: str = ""):
    tracks = _tracks(q, artist, album)
    return templates.TemplateResponse(request, "partials/tracks.html", {"tracks": tracks})


@router.post("/api/scan")
def scan():
    res = scan_media()
    return JSONResponse(res)


def _list_playlists():
    with conn_ctx() as c:
        rows = c.execute("SELECT * FROM playlists ORDER BY name").fetchall()
    from ..models import Playlist
    return [Playlist.from_row(r) for r in rows]


@router.get("/api/playlists-list", response_class=HTMLResponse)
def playlists_list_partial(request: Request):
    pls = _list_playlists()
    return templates.TemplateResponse(request, "partials/playlists.html", {"playlists": pls})


@router.post("/api/tracks/{track_id}/edit")
def edit_track(track_id: int, title: str = Form(""), artist: str = Form(""), album: str = Form(""),
               write_tags_flag: str = Form("0")):
    with conn_ctx() as c:
        row = c.execute("SELECT * FROM tracks WHERE id=?", (track_id,)).fetchone()
        if not row:
            return JSONResponse({"error": "introuvable"}, status_code=404)
        c.execute(
            "UPDATE tracks SET title=?, artist=?, album=? WHERE id=?",
            (title or None, artist or None, album or None, track_id),
        )
        path = row["path"]
    if write_tags_flag == "1":
        try:
            write_tags(path, title, artist, album)
        except Exception as e:
            log.warning("write_tags erreur: %s", e)
    return JSONResponse({"ok": True})


@router.get("/api/tracks/{track_id}")
def track_detail(track_id: int):
    with conn_ctx() as c:
        row = c.execute("SELECT * FROM tracks WHERE id=?", (track_id,)).fetchone()
    if not row:
        return JSONResponse({"error": "introuvable"}, status_code=404)
    from ..models import Track
    return JSONResponse(Track.from_row(row).to_dict())


@router.delete("/api/tracks/{track_id}")
def delete_track(track_id: int):
    with conn_ctx() as c:
        c.execute("DELETE FROM tracks WHERE id=?", (track_id,))
    return JSONResponse({"ok": True})
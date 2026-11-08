"""Routes playlists : CRUD, ajout/retrait/réordonnancement."""
from __future__ import annotations

import json

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse

from .. import templates
from ..database import conn_ctx
from ..models import Playlist

router = APIRouter()


def _list_playlists() -> list[Playlist]:
    with conn_ctx() as c:
        rows = c.execute("SELECT * FROM playlists ORDER BY name").fetchall()
    return [Playlist.from_row(r) for r in rows]


def _playlist_tracks(playlist_id: int) -> list[dict]:
    with conn_ctx() as c:
        rows = c.execute(
            """SELECT t.*, pt.position FROM tracks t
               JOIN playlist_tracks pt ON pt.track_id = t.id
               WHERE pt.playlist_id = ? ORDER BY pt.position""",
            (playlist_id,),
        ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        out.append(d)
    return out


@router.get("/playlists", response_class=HTMLResponse)
def playlists_page(request: Request):
    pls = _list_playlists()
    pls_simple = [{"playlist": p} for p in pls]
    return templates.TemplateResponse(request, "playlists_page.html", {"playlists": pls_simple})


@router.get("/api/playlists", response_class=HTMLResponse)
def playlists_partial(request: Request):
    pls = _list_playlists()
    return templates.TemplateResponse(request, "partials/playlists.html", {"playlists": pls})


@router.post("/api/playlists")
def create_playlist(name: str = Form(...)):
    name = name.strip()
    if not name:
        return JSONResponse({"error": "empty name"}, status_code=400)
    with conn_ctx() as c:
        c.execute("INSERT INTO playlists (name) VALUES (?)", (name,))
        pid = c.execute("SELECT last_insert_rowid()").fetchone()[0]
    return JSONResponse({"id": pid, "name": name})


@router.put("/api/playlists/{playlist_id}")
def rename_playlist(playlist_id: int, name: str = Form(...)):
    name = name.strip()
    if not name:
        return JSONResponse({"error": "empty name"}, status_code=400)
    with conn_ctx() as c:
        c.execute("UPDATE playlists SET name=?, updated_at=datetime('now') WHERE id=?", (name, playlist_id))
    return JSONResponse({"ok": True})


@router.delete("/api/playlists/{playlist_id}")
def delete_playlist(playlist_id: int):
    with conn_ctx() as c:
        c.execute("DELETE FROM playlists WHERE id=?", (playlist_id,))
    return JSONResponse({"ok": True})


@router.get("/api/playlists/{playlist_id}/tracks", response_class=HTMLResponse)
def playlist_tracks_partial(request: Request, playlist_id: int):
    tracks = _playlist_tracks(playlist_id)
    return templates.TemplateResponse(request, "partials/playlist_tracks.html", {
        "tracks": tracks, "playlist_id": playlist_id,
    })


@router.post("/api/playlists/{playlist_id}/tracks")
def add_tracks(playlist_id: int, track_ids: str = Form(...)):
    # track_ids: liste séparée par virgules
    ids = [int(x) for x in track_ids.split(",") if x.strip().isdigit()]
    with conn_ctx() as c:
        # position de départ
        row = c.execute("SELECT MAX(position) AS m FROM playlist_tracks WHERE playlist_id=?", (playlist_id,)).fetchone()
        pos = (row["m"] or 0) + 1
        for tid in ids:
            exists = c.execute(
                "SELECT 1 FROM playlist_tracks WHERE playlist_id=? AND track_id=?", (playlist_id, tid)
            ).fetchone()
            if exists:
                continue
            # réajuste position si conflit
            while c.execute(
                "SELECT 1 FROM playlist_tracks WHERE playlist_id=? AND position=?", (playlist_id, pos)
            ).fetchone():
                pos += 1
            c.execute(
                "INSERT INTO playlist_tracks (playlist_id, track_id, position) VALUES (?,?,?)",
                (playlist_id, tid, pos),
            )
            pos += 1
    return JSONResponse({"ok": True})


@router.delete("/api/playlists/{playlist_id}/tracks/{track_id}")
def remove_track(playlist_id: int, track_id: int):
    with conn_ctx() as c:
        c.execute("DELETE FROM playlist_tracks WHERE playlist_id=? AND track_id=?", (playlist_id, track_id))
        # réindexer positions
        rows = c.execute(
            "SELECT track_id FROM playlist_tracks WHERE playlist_id=? ORDER BY position", (playlist_id,)
        ).fetchall()
        for i, r in enumerate(rows, start=1):
            c.execute("UPDATE playlist_tracks SET position=? WHERE playlist_id=? AND track_id=?",
                      (i, playlist_id, r["track_id"]))
    return JSONResponse({"ok": True})


@router.post("/api/playlists/{playlist_id}/reorder")
def reorder(playlist_id: int, order: str = Form(...)):
    # order: ids séparés par virgules dans le nouvel ordre
    ids = [int(x) for x in order.split(",") if x.strip().isdigit()]
    with conn_ctx() as c:
        # évite les conflits de contrainte UNIQUE : on réinsère
        existing = [r[0] for r in c.execute(
            "SELECT track_id FROM playlist_tracks WHERE playlist_id=? ORDER BY position", (playlist_id,)).fetchall()]
        existing_set = set(existing)
        ids = [i for i in ids if i in existing_set]
        missing = [t for t in existing if t not in ids]
        final = ids + missing
        c.execute("DELETE FROM playlist_tracks WHERE playlist_id=?", (playlist_id,))
        for i, tid in enumerate(final, start=1):
            c.execute(
                "INSERT INTO playlist_tracks (playlist_id, track_id, position) VALUES (?,?,?)",
                (playlist_id, tid, i),
            )
    return JSONResponse({"ok": True})


@router.get("/api/playlists/{playlist_id}/tracks.json")
def playlist_tracks_json(playlist_id: int):
    tracks = _playlist_tracks(playlist_id)
    return JSONResponse(tracks)
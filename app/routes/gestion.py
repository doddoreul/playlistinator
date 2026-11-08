"""Page de gestion : chansons, playlists, doublons."""
from __future__ import annotations

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse

from .. import templates
from ..database import conn_ctx
from ..models import Track, Playlist

router = APIRouter()


def _tracks():
    with conn_ctx() as c:
        rows = c.execute("SELECT * FROM tracks ORDER BY artist, title").fetchall()
    return [Track.from_row(r) for r in rows]


def _artists():
    with conn_ctx() as c:
        rows = c.execute(
            "SELECT artist AS name, COUNT(*) AS n FROM tracks WHERE artist IS NOT NULL GROUP BY artist ORDER BY artist"
        ).fetchall()
    return [{"name": r["name"], "count": r["n"]} for r in rows]


def _albums():
    with conn_ctx() as c:
        rows = c.execute(
            "SELECT album AS name, artist, COUNT(*) AS n FROM tracks WHERE album IS NOT NULL GROUP BY album, artist ORDER BY album"
        ).fetchall()
    return [{"name": r["name"], "artist": r["artist"], "count": r["n"]} for r in rows]


def _playlists():
    with conn_ctx() as c:
        rows = c.execute("SELECT * FROM playlists ORDER BY name").fetchall()
    return [Playlist.from_row(r) for r in rows]


def _duplicates():
    with conn_ctx() as c:
        rows = c.execute(
            """SELECT title, artist, COUNT(*) AS n FROM tracks
               WHERE title IS NOT NULL GROUP BY title, artist HAVING n > 1"""
        ).fetchall()
    dups = []
    for r in rows:
        with conn_ctx() as c2:
            trs = c2.execute(
                "SELECT * FROM tracks WHERE title=? AND (artist IS ? OR artist=?)",
                (r["title"], r["artist"], r["artist"]),
            ).fetchall()
        dups.append({"title": r["title"], "artist": r["artist"], "tracks": [Track.from_row(x) for x in trs]})
    return dups


@router.get("/gestion", response_class=HTMLResponse)
def gestion_page(request: Request):
    return templates.TemplateResponse(request, "gestion.html", {
        "tracks": _tracks(),
        "artists": _artists(),
        "albums": _albums(),
        "playlists": _playlists(),
        "duplicates": _duplicates(),
    })


@router.post("/api/tracks")
def add_track(path: str = Form(...), title: str = Form(""), artist: str = Form(""), album: str = Form("")):
    from pathlib import Path
    p = Path(path)
    if not p.is_file():
        return JSONResponse({"error": "fichier introuvable"}, status_code=400)
    import hashlib
    h = hashlib.sha256(p.read_bytes()).hexdigest()
    with conn_ctx() as c:
        dup = c.execute("SELECT id FROM tracks WHERE file_hash=?", (h,)).fetchone()
        if dup:
            return JSONResponse({"error": "doublon détecté, merci de vérifier manuellement via la section doublons", "duplicate_id": dup["id"]}, status_code=409)
        from app.services.metadata import build_metadata
        meta = build_metadata(p)
        c.execute(
            """INSERT INTO tracks (path, title, artist, album, duration, file_hash) VALUES (?,?,?,?,?,?)""",
            (str(p.resolve()), title or meta.title, artist or meta.artist, album or meta.album, meta.duration, h),
        )
        tid = c.execute("SELECT last_insert_rowid()").fetchone()[0]
    return JSONResponse({"id": tid})


@router.post("/api/tracks/{track_id}/cover-search")
def cover_search(track_id: int):
    with conn_ctx() as c:
        row = c.execute("SELECT artist, title FROM tracks WHERE id=?", (track_id,)).fetchone()
    if not row:
        return JSONResponse({"error": "introuvable"}, status_code=404)
    from app.services.covers import search_cover
    res = search_cover(row["artist"], row["title"])
    return JSONResponse({"results": res})
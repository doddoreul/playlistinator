"""Plugin d'import YouTube via yt-dlp (vidéos et playlists)."""
from __future__ import annotations

import asyncio
import logging
import uuid
from pathlib import Path

import yt_dlp

from app.services.scanner import index_file

log = logging.getLogger("playlistinator.youtube")

_jobs: dict = {}


def _download_one(url: str, media_dir: Path, noplaylist: bool = True) -> Path:
    opts = {
        "format": "bestaudio/best",
        "outtmpl": str(media_dir / "%(title)s.%(ext)s"),
        "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"}],
        "quiet": True,
        "no_warnings": True,
        "noplaylist": noplaylist,
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)
        prepared = ydl.prepare_filename(info)
    final = Path(prepared).with_suffix(".mp3")
    if not final.exists():
        candidates = sorted(media_dir.glob("*.mp3"), key=lambda p: p.stat().st_mtime, reverse=True)
        if candidates:
            final = candidates[0]
    if not final.exists():
        raise RuntimeError("fichier mp3 introuvable après téléchargement")
    return final


def _download_playlist(url: str, media_dir: Path) -> tuple[str, list[Path]]:
    before = set(media_dir.glob("*.mp3"))
    title = "Playlist YouTube"
    opts = {
        "format": "bestaudio/best",
        "outtmpl": str(media_dir / "%(playlist_index)s - %(title)s.%(ext)s"),
        "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"}],
        "quiet": True,
        "no_warnings": True,
        "noplaylist": False,
        "ignoreerrors": True,
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)
        if isinstance(info, dict) and info.get("title"):
            title = info["title"]
    after = set(media_dir.glob("*.mp3"))
    return title, sorted(after - before)


async def _run_job(job_id: str, mode: str, urls: list[str], media_dir: Path):
    job = _jobs[job_id]
    job["total"] = len(urls)
    job["current"] = 0
    job["results"] = []
    for i, url in enumerate(urls, start=1):
        job["current"] = i
        url = url.strip()
        if not url:
            continue
        if mode == "playlist":
            job["status"] = f"playlist {i}/{len(urls)}"
            try:
                title, paths = await asyncio.to_thread(_download_playlist, url, media_dir)
                tids = []
                dup_count = 0
                for p in paths:
                    from app.services.metadata import file_hash
                    from app.database import conn_ctx
                    h = await asyncio.to_thread(file_hash, p)
                    with conn_ctx() as c:
                        dup = c.execute("SELECT id FROM tracks WHERE file_hash=?", (h,)).fetchone()
                    if dup:
                        try:
                            p.unlink()
                        except Exception:
                            pass
                        dup_count += 1
                    else:
                        tid = await asyncio.to_thread(index_file, p)
                        tids.append(tid)
                # créer une playlist dans le logiciel
                if tids:
                    from app.database import conn_ctx as _cc
                    with _cc() as c:
                        c.execute("INSERT INTO playlists (name) VALUES (?)", (title,))
                        pid = c.execute("SELECT last_insert_rowid()").fetchone()[0]
                        pos = 1
                        for tid in tids:
                            c.execute("INSERT INTO playlist_tracks (playlist_id, track_id, position) VALUES (?,?,?)", (pid, tid, pos))
                            pos += 1
                msg = "doublon détecté, merci de vérifier manuellement via la section doublons" if dup_count else None
                job["results"].append({"url": url, "ok": True, "count": len(paths), "track_ids": tids, "playlist": title, "duplicates": dup_count, "error": msg})
            except Exception as e:
                log.warning("YouTube playlist erreur %s: %s", url, e)
                job["results"].append({"url": url, "ok": False, "error": str(e)})
        else:
            job["status"] = f"téléchargement {i}/{len(urls)}"
            try:
                path = await asyncio.to_thread(_download_one, url, media_dir, True)
                from app.services.metadata import file_hash
                from app.database import conn_ctx
                h = await asyncio.to_thread(file_hash, path)
                with conn_ctx() as c:
                    dup = c.execute("SELECT id FROM tracks WHERE file_hash=?", (h,)).fetchone()
                if dup:
                    try:
                        path.unlink()
                    except Exception:
                        pass
                    job["results"].append({"url": url, "ok": False, "error": "doublon détecté, merci de vérifier manuellement via la section doublons", "duplicate_id": dup["id"]})
                else:
                    tid = await asyncio.to_thread(index_file, path)
                    job["results"].append({"url": url, "ok": True, "track_id": tid})
            except Exception as e:
                log.warning("YouTube import erreur %s: %s", url, e)
                job["results"].append({"url": url, "ok": False, "error": str(e)})
    job["status"] = "terminé"
    job["done"] = True


def register(app, context):
    from fastapi import APIRouter, Form, Request
    from fastapi.responses import HTMLResponse, JSONResponse

    cfg = context["config"]
    media_dir = cfg.media_dir
    templates = context["templates"]

    router = APIRouter()

    @router.get("/modal", response_class=HTMLResponse)
    def modal():
        from jinja2 import Environment, FileSystemLoader
        d = Path(__file__).resolve().parent
        env = Environment(loader=FileSystemLoader(str(d)))
        template = env.get_template("youtube_modal.html")
        return HTMLResponse(template.render())

    @router.post("/import")
    async def start_import(mode: str = Form("videos"), urls: str = Form(...)):
        lines = [u for u in urls.splitlines() if u.strip()]
        if not lines:
            return JSONResponse({"error": "aucune URL"}, status_code=400)
        if mode not in ("videos", "playlist"):
            mode = "videos"
        # en mode playlist, on ne garde qu'une URL (la première)
        if mode == "playlist":
            lines = [lines[0]]
        jid = uuid.uuid4().hex
        _jobs[jid] = {"id": jid, "status": "démarrage", "current": 0, "total": len(lines), "done": False, "results": [], "mode": mode}
        asyncio.create_task(_run_job(jid, mode, lines, media_dir))
        return JSONResponse({"job_id": jid})

    @router.get("/status/{job_id}")
    def status(job_id: str):
        job = _jobs.get(job_id)
        if not job:
            return JSONResponse({"error": "job inconnu"}, status_code=404)
        return JSONResponse(job)

    app.include_router(router, prefix="/plugins/youtube", tags=["youtube"])
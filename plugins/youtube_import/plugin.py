"""Plugin d'import YouTube via yt-dlp (vidéos et playlists)."""
from __future__ import annotations

import asyncio
import logging
import uuid
from pathlib import Path

import httpx
import yt_dlp

from app.services.scanner import index_file

log = logging.getLogger("playlistinator.youtube")

_jobs: dict = {}


import re as _re


def _safe_name(s: str) -> str:
    s = (s or "").strip()
    # supprime les caractères invalides pour un nom de fichier
    s = _re.sub(r'[<>:"/\\\\|?*]', "", s)
    s = _re.sub(r"\s+", " ", s).strip(". ")
    if not s:
        s = "video"
    return s[:120]


def _thumb_url(info: dict) -> str | None:
    t = info.get("thumbnail")
    if t:
        return t
    vid = info.get("id")
    if vid:
        return f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg"
    return None


def _artist(info: dict) -> str | None:
    return info.get("artist") or info.get("uploader") or info.get("channel")


def _trim_artist_from_title(title: str | None, artist: str | None) -> str | None:
    if not title:
        return title
    t = title.strip()
    if artist:
        a = artist.strip()
        seps = [" - ", " – ", " — ", ": ", " | ", " / "]
        low_t = t.lower()
        low_a = a.lower()
        for sep in seps:
            if low_t.startswith(low_a + sep.lower()):
                t = t[len(a) + len(sep):].strip()
                low_t = t.lower()
                break
        for sep in seps:
            if low_t.endswith(sep.lower() + low_a):
                t = t[:-(len(a) + len(sep))].strip()
                low_t = t.lower()
                break
    return _clean_title(t)


def _clean_title(title: str | None) -> str | None:
    if not title:
        return title
    import re as _re
    t = title
    # retire les mentions officielles / clips
    patterns = [
        r"\(?\[?\s*(official\s*(music\s*)?video|official\s*audio|clip\s*officiel|lyric\s*video|audio\s*officiel|official)\s*\)?\]?",
        r"\(?\[?\s*(hd|4k|remaster(ed)?|visualizer)\s*\)?\]?",
    ]
    for pat in patterns:
        t = _re.sub(pat, "", t, flags=_re.IGNORECASE)
    # nettoie espaces et séparateurs orphelins
    t = _re.sub(r"\s{2,}", " ", t).strip(" -–—:|/")
    t = t.strip()
    return t or title


def _download_thumb(url: str, dest: Path) -> bool:
    try:
        with httpx.Client(timeout=20.0, follow_redirects=True) as c:
            r = c.get(url)
            r.raise_for_status()
            dest.write_bytes(r.content)
        return True
    except Exception as e:
        log.warning("thumbnail erreur: %s", e)
        return False


def _download_one(url: str, media_dir: Path) -> tuple[Path, str | None, str | None, str | None]:
    opts = {
        "format": "bestaudio/best",
        "outtmpl": str(media_dir / "%(id)s.%(ext)s"),
        "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"}],
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
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
    # renomme en nom lisible
    safe = _safe_name(info.get("title") or info.get("id") or "video")
    dest = media_dir / (safe + ".mp3")
    if dest != final:
        if dest.exists():
            dest = media_dir / (safe + " [" + str(info.get("id", "")) + "].mp3")
        try:
            final.rename(dest)
            final = dest
        except Exception:
            pass
    return final, info.get("title"), _artist(info), _thumb_url(info)


def _download_playlist(url: str, media_dir: Path) -> tuple[str, list[tuple[Path, str | None, str | None, str | None]]]:
    before = set(media_dir.glob("*.mp3"))
    title = "Playlist YouTube"
    opts = {
        "format": "bestaudio/best",
        "outtmpl": str(media_dir / "%(id)s.%(ext)s"),
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
        entries = list(info.get("entries") or [])
    after = set(media_dir.glob("*.mp3"))
    new_files = sorted(after - before, key=lambda p: p.stat().st_mtime)
    # map entries -> files by _filename if available, else by order
    mapped = False
    paths_by_entry = []
    for e in entries:
        fn = e.get("_filename") if isinstance(e, dict) else None
        if fn:
            p = Path(fn).with_suffix(".mp3")
            if p.exists():
                paths_by_entry.append(p)
                mapped = True
    if not mapped or len(paths_by_entry) != len(entries):
        paths_by_entry = new_files
    results: list[tuple[Path, str | None, str | None, str | None]] = []
    for i, e in enumerate(entries):
        if not isinstance(e, dict):
            continue
        path = paths_by_entry[i] if i < len(paths_by_entry) else None
        if path is None or not path.exists():
            continue
        # renomme en nom lisible
        safe = _safe_name(e.get("title") or e.get("id") or "video")
        dest = media_dir / (safe + ".mp3")
        if dest != path:
            if dest.exists():
                dest = media_dir / (safe + " [" + str(e.get("id", "")) + "].mp3")
            try:
                path.rename(dest)
                path = dest
            except Exception:
                pass
        results.append((path, e.get("title"), _artist(e), _thumb_url(e)))
    if not results and new_files:
        for p in new_files:
            results.append((p, None, None, None))
    return title, results


async def _apply_metadata(tid: int, title: str | None, artist: str | None, thumb_url: str | None, media_dir: Path, album: str | None = None):
    from app.database import conn_ctx
    from app.config import get_config
    cfg = get_config()
    cover_path = None
    if thumb_url:
        cover_dir = cfg.media_dir / ".covers"
        cover_dir.mkdir(exist_ok=True)
        dest = cover_dir / f"yt_{tid}.jpg"
        ok = await asyncio.to_thread(_download_thumb, thumb_url, dest)
        if ok:
            cover_path = str(dest.resolve())
    with conn_ctx() as c:
        row = c.execute("SELECT title, artist, cover_path, album FROM tracks WHERE id=?", (tid,)).fetchone()
        updates = []
        params = []
        if title:
            title = _trim_artist_from_title(title, artist)
            if title:
                updates.append("title=?")
                params.append(title)
        if artist:
            updates.append("artist=?")
            params.append(artist)
        if album:
            updates.append("album=?")
            params.append(album)
        if cover_path:
            updates.append("cover_path=?")
            params.append(cover_path)
        if updates:
            params.append(tid)
            c.execute(f"UPDATE tracks SET {', '.join(updates)} WHERE id=?", params)


async def _run_job(job_id: str, mode: str, urls: list[str], media_dir: Path):
    job = _jobs[job_id]
    job["total"] = len(urls)
    job["current"] = 0
    job["results"] = []
    job["log"] = []
    job["current_url"] = ""
    for i, url in enumerate(urls, start=1):
        job["current"] = i
        url = url.strip()
        if not url:
            continue
        job["current_url"] = url
        if mode in ("playlist", "album"):
            job["status"] = f"playlist {i}/{len(urls)}"
            try:
                title, items = await asyncio.to_thread(_download_playlist, url, media_dir)
                tids = []
                dup_count = 0
                for path, title_v, artist, thumb in items:
                    from app.services.metadata import file_hash
                    from app.database import conn_ctx
                    h = await asyncio.to_thread(file_hash, path)
                    with conn_ctx() as c:
                        dup = c.execute("SELECT id FROM tracks WHERE file_hash=?", (h,)).fetchone()
                    if dup:
                        # ne pas supprimer le fichier, prévenir l'utilisateur
                        dup_count += 1
                    else:
                        tid = await asyncio.to_thread(index_file, path)
                        album_name = title if mode == "album" else None
                        await _apply_metadata(tid, title_v, artist, thumb, media_dir, album=album_name)
                        tids.append(tid)
                # créer une playlist dans le logiciel (mode playlist uniquement)
                if mode == "playlist" and tids:
                    from app.database import conn_ctx as _cc
                    with _cc() as c:
                        c.execute("INSERT INTO playlists (name) VALUES (?)", (title,))
                        pid = c.execute("SELECT last_insert_rowid()").fetchone()[0]
                        pos = 1
                        for tid in tids:
                            c.execute("INSERT INTO playlist_tracks (playlist_id, track_id, position) VALUES (?,?,?)", (pid, tid, pos))
                            pos += 1
                msg = "doublon détecté, merci de vérifier manuellement via la section doublons" if dup_count else None
                entry = {"url": url, "ok": True, "count": len(items), "track_ids": tids, "playlist": title if mode == "playlist" else None, "album": title if mode == "album" else None, "duplicates": dup_count, "error": msg}
                job["results"].append(entry)
                job["log"].append(entry)
            except Exception as e:
                log.warning("YouTube playlist erreur %s: %s", url, e)
                entry = {"url": url, "ok": False, "error": str(e)}
                job["results"].append(entry)
                job["log"].append(entry)
        else:
            job["status"] = f"téléchargement {i}/{len(urls)}"
            try:
                path, title_v, artist, thumb = await asyncio.to_thread(_download_one, url, media_dir)
                from app.services.metadata import file_hash
                from app.database import conn_ctx
                h = await asyncio.to_thread(file_hash, path)
                with conn_ctx() as c:
                    dup = c.execute("SELECT id FROM tracks WHERE file_hash=?", (h,)).fetchone()
                if dup:
                    # ne pas supprimer le fichier, prévenir l'utilisateur
                    entry = {"url": url, "ok": False, "error": "doublon détecté, merci de vérifier manuellement via la section doublons", "duplicate_id": dup["id"]}
                    job["results"].append(entry)
                    job["log"].append(entry)
                else:
                    tid = await asyncio.to_thread(index_file, path)
                    await _apply_metadata(tid, title_v, artist, thumb, media_dir)
                    entry = {"url": url, "ok": True, "track_id": tid}
                    job["results"].append(entry)
                    job["log"].append(entry)
            except Exception as e:
                log.warning("YouTube import erreur %s: %s", url, e)
                entry = {"url": url, "ok": False, "error": str(e)}
                job["results"].append(entry)
                job["log"].append(entry)
    job["status"] = "terminé"
    job["done"] = True


def register(app, context):
    from fastapi import APIRouter, Form
    from fastapi.responses import HTMLResponse, JSONResponse

    cfg = context["config"]
    media_dir = cfg.media_dir
    templates = context["templates"]

    router = APIRouter()

    @router.get("/import-tab", response_class=HTMLResponse)
    def import_tab():
        from jinja2 import Environment, FileSystemLoader
        d = Path(__file__).resolve().parent
        env = Environment(loader=FileSystemLoader(str(d)))
        template = env.get_template("youtube_modal.html")
        return HTMLResponse(template.render())

    @router.get("/modal", response_class=HTMLResponse)
    def modal():
        return import_tab()

    @router.post("/import")
    async def start_import(mode: str = Form("videos"), urls: str = Form(...)):
        lines = [u for u in urls.splitlines() if u.strip()]
        if not lines:
            return JSONResponse({"error": "aucune URL"}, status_code=400)
        if mode not in ("videos", "playlist", "album"):
            mode = "videos"
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
    if "register_import_tab" in context:
        context["register_import_tab"]({"id": "youtube", "label": "YouTube", "content_url": "/plugins/youtube/import-tab"})
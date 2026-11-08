"""Import de musique par URL : jobs avec progression."""
from __future__ import annotations

import asyncio
import logging
import uuid
from pathlib import Path
from typing import Optional

from .audio_source import AudioSource, DirectUrlSource, validate_url
from .metadata import build_metadata, file_hash
from ..config import get_config
from ..database import conn_ctx

log = logging.getLogger("playlistinator.importer")

_jobs: dict[str, dict] = {}


def create_job(url: str) -> str:
    jid = uuid.uuid4().hex
    _jobs[jid] = {"id": jid, "url": url, "status": "pending", "progress": 0, "total": 0,
                   "error": None, "track_id": None, "done": False}
    return jid


def get_job(jid: str) -> Optional[dict]:
    return _jobs.get(jid)


async def run_import(jid: str, source: Optional[AudioSource] = None) -> None:
    job = _jobs[jid]
    url = job["url"]
    cfg = get_config()
    ok, msg = validate_url(url)
    if not ok:
        job["status"] = "error"
        job["error"] = msg
        job["done"] = True
        return

    source = source or DirectUrlSource()

    def progress_cb(downloaded, total):
        job["progress"] = downloaded
        job["total"] = total
        job["status"] = "downloading"

    try:
        job["status"] = "downloading"
        path = await source.download(url, cfg.media_dir, cfg.max_import_size, progress_cb)
    except Exception as e:
        log.warning("Import erreur: %s", e)
        job["status"] = "error"
        job["error"] = str(e)
        job["done"] = True
        return

    # parsing métadonnées
    job["status"] = "indexing"
    try:
        meta = build_metadata(path)
        h = file_hash(path)
        cover_path = None
        if meta.cover_bytes:
            cover_dir = cfg.media_dir / ".covers"
            cover_dir.mkdir(exist_ok=True)
            cover_path = str(cover_dir / f"{h}.{meta.cover_ext or 'jpg'}")
            if not Path(cover_path).exists():
                Path(cover_path).write_bytes(meta.cover_bytes)
        with conn_ctx() as c:
            dup = c.execute("SELECT id FROM tracks WHERE file_hash = ?", (h,)).fetchone()
            if dup is not None:
                try:
                    path.unlink()
                except Exception:
                    pass
                job["status"] = "duplicate"
                job["error"] = "doublon détecté, merci de vérifier manuellement via la section doublons"
                job["track_id"] = dup["id"]
                job["done"] = True
                return
            c.execute(
                """INSERT INTO tracks (path, title, artist, album, duration, cover_path, file_hash)
                   VALUES (?,?,?,?,?,?,?)""",
                (str(path.resolve()), meta.title, meta.artist, meta.album, meta.duration, cover_path, h),
            )
            tid = c.execute("SELECT last_insert_rowid()").fetchone()[0]
        job["track_id"] = tid
        job["status"] = "done"
    except Exception as e:
        log.exception("Indexation erreur")
        job["status"] = "error"
        job["error"] = str(e)
    finally:
        job["done"] = True
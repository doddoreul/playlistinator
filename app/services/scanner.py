"""Scan du dossier media et indexation des MP3."""
from __future__ import annotations

import logging
from pathlib import Path

from .metadata import build_metadata, file_hash
from ..config import get_config
from ..database import conn_ctx
from ..models import Track

log = logging.getLogger("playlistinator.scanner")


def scan_media(patterns: list[str] | None = None) -> dict:
    cfg = get_config()
    root = cfg.media_dir
    patterns = patterns or cfg.filename_patterns
    added = 0
    updated = 0
    skipped = 0
    errors = []
    for p in sorted(root.rglob("*.mp3")):
        try:
            rel = str(p.resolve())
            h = file_hash(p)
            meta = build_metadata(p, patterns)
            # pochette intégrée -> sauvegarde si présente
            cover_path = None
            if meta.cover_bytes:
                cover_dir = cfg.media_dir / ".covers"
                cover_dir.mkdir(exist_ok=True)
                cover_path = str(cover_dir / f"{h}.{meta.cover_ext or 'jpg'}")
                if not Path(cover_path).exists():
                    Path(cover_path).write_bytes(meta.cover_bytes)

            with conn_ctx() as c:
                row = c.execute("SELECT id, file_hash FROM tracks WHERE path = ?", (rel,)).fetchone()
                if row is not None:
                    if row["file_hash"] == h:
                        skipped += 1
                        continue
                    c.execute(
                        """UPDATE tracks SET title=?, artist=?, album=?, duration=?, cover_path=?, file_hash=?
                           WHERE id=?""",
                        (meta.title, meta.artist, meta.album, meta.duration, cover_path, h, row["id"]),
                    )
                    updated += 1
                    continue
                # doublon par hash (même fichier ailleurs)
                dup = c.execute("SELECT id FROM tracks WHERE file_hash = ?", (h,)).fetchone()
                if dup is not None:
                    skipped += 1
                    continue
                c.execute(
                    """INSERT INTO tracks (path, title, artist, album, duration, cover_path, file_hash)
                       VALUES (?,?,?,?,?,?,?)""",
                    (rel, meta.title, meta.artist, meta.album, meta.duration, cover_path, h),
                )
                added += 1
        except Exception as e:
            log.exception("Erreur scan %s", p)
            errors.append({"path": str(p), "error": str(e)})
    return {"added": added, "updated": updated, "skipped": skipped, "errors": errors}


def cleanup_orphans() -> int:
    """Supprime les pistes dont le fichier n'existe plus. Renvoie le nombre supprimé."""
    from pathlib import Path
    removed = 0
    with conn_ctx() as c:
        rows = c.execute("SELECT id, path FROM tracks").fetchall()
        for r in rows:
            if not Path(r["path"]).is_file():
                c.execute("DELETE FROM tracks WHERE id=?", (r["id"],))
                removed += 1
    return removed


def index_file(path, cfg=None) -> int | None:
    """Indexe un fichier audio déjà présent. Renvoie l'id de la piste (existant ou nouveau), ou None en erreur."""
    from ..config import get_config
    cfg = cfg or get_config()
    p = Path(path)
    if not p.is_file():
        return None
    try:
        meta = build_metadata(p)
        h = file_hash(p)
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
                return dup["id"]
            c.execute(
                """INSERT INTO tracks (path, title, artist, album, duration, cover_path, file_hash)
                   VALUES (?,?,?,?,?,?,?)""",
                (str(p.resolve()), meta.title, meta.artist, meta.album, meta.duration, cover_path, h),
            )
            return c.execute("SELECT last_insert_rowid()").fetchone()[0]
    except Exception:
        log.exception("Erreur indexation %s", p)
        return None
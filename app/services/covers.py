"""Recherche de pochettes via MusicBrainz + Cover Art Archive."""
from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Optional

import httpx

from ..config import get_config
from ..database import conn_ctx

log = logging.getLogger("playlistinator.covers")

_last_request = [0.0]


def _rate_limit() -> None:
    now = time.time()
    delta = now - _last_request[0]
    if delta < 1.0:
        time.sleep(1.0 - delta)
    _last_request[0] = time.time()


def search_cover(artist: Optional[str], title: Optional[str]) -> list[dict]:
    """Renvoie une liste de {image_url, source}. Jamais au démarrage."""
    cfg = get_config()
    results = []
    # cache
    with conn_ctx() as c:
        row = c.execute(
            "SELECT local_path, image_url FROM cover_cache WHERE artist=? AND title=?",
            (artist, title),
        ).fetchone()
        if row and row["local_path"]:
            return [{"image_url": row["image_url"], "local_path": row["local_path"], "source": "cache"}]
        if row and row["image_url"]:
            return [{"image_url": row["image_url"], "local_path": None, "source": "cache"}]

    if not (artist or title):
        return results

    query_parts = []
    if artist:
        query_parts.append(f'artist:"{artist}"')
    if title:
        query_parts.append(f'recording:"{title}"')
    query = " AND ".join(query_parts) if query_parts else (title or "")

    _rate_limit()
    headers = {"User-Agent": cfg.user_agent, "Accept": "application/json"}
    try:
        with httpx.Client(timeout=15.0, headers=headers) as client:
            r = client.get("https://musicbrainz.org/ws/2/recording", params={"query": query, "fmt": "json", "limit": 5})
            r.raise_for_status()
            data = r.json()
    except Exception as e:
        log.warning("MusicBrainz erreur: %s", e)
        return results

    recordings = data.get("recordings", []) or []
    # récupérer les release ids
    release_ids = []
    for rec in recordings[:3]:
        for rel in (rec.get("releases") or [])[:2]:
            rid = rel.get("id")
            if rid and rid not in release_ids:
                release_ids.append(rid)

    for rid in release_ids[:3]:
        _rate_limit()
        try:
            with httpx.Client(timeout=15.0, headers={"User-Agent": cfg.user_agent}, follow_redirects=True) as client:
                r = client.get(f"https://coverartarchive.org/release/{rid}")
                if r.status_code == 404:
                    continue
                r.raise_for_status()
                cdata = r.json()
        except Exception as e:
            log.warning("Cover Art erreur: %s", e)
            continue
        for img in cdata.get("images", []) or []:
            if img.get("front"):
                url = img.get("image") or img.get("thumbnails", {}).get("large")
                if url:
                    results.append({"image_url": url, "release_id": rid, "source": "coverartarchive"})
                    break
        if results:
            break

    # cache le premier résultat
    if results:
        with conn_ctx() as c:
            c.execute(
                """INSERT INTO cover_cache (artist, title, image_url) VALUES (?,?,?)
                   ON CONFLICT(artist,title) DO UPDATE SET image_url=excluded.image_url, fetched_at=datetime('now')""",
                (artist, title, results[0]["image_url"]),
            )
    return results


def download_cover(image_url: str, track_id: int) -> Optional[str]:
    """Télécharge une image de pochette dans media/.covers et renvoie le chemin local."""
    cfg = get_config()
    cover_dir = cfg.media_dir / ".covers"
    cover_dir.mkdir(exist_ok=True)
    try:
        headers = {"User-Agent": cfg.user_agent}
        with httpx.Client(timeout=20.0, headers=headers, follow_redirects=True) as client:
            r = client.get(image_url)
            r.raise_for_status()
            data = r.content
        if len(data) > 5 * 1024 * 1024:
            return None
        ext = "jpg"
        ct = r.headers.get("content-type", "")
        if "png" in ct:
            ext = "png"
        path = cover_dir / f"track_{track_id}.{ext}"
        path.write_bytes(data)
        return str(path.resolve())
    except Exception as e:
        log.warning("download_cover erreur: %s", e)
        return None
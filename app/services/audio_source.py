"""Interface AudioSource + implémentation DirectUrlSource."""
from __future__ import annotations

import logging
import os
import re
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

log = logging.getLogger("playlistinator.audio_source")

AUDIO_EXTENSIONS = {".mp3", ".mpeg", ".mpga"}
MAX_DEFAULT = 50 * 1024 * 1024


def validate_url(url: str) -> tuple[bool, str]:
    """Valide une URL (scheme http/https, host présent). Renvoie (ok, message)."""
    if not url or not isinstance(url, str):
        return False, "URL vide"
    url = url.strip()
    try:
        p = urlparse(url)
    except Exception:
        return False, "URL invalide"
    if p.scheme not in ("http", "https"):
        return False, "Schéma non supporté (http/https attendu)"
    if not p.netloc:
        return False, "Hôte manquant"
    # protection basique : pas de localhost/loopback pour éviter SSRF ? On garde permissif mais log.
    return True, "ok"


class AudioSource(ABC):
    @abstractmethod
    async def download(self, url: str, dest_dir: Path, max_size: int, progress_cb=None) -> Path:
        """Télécharge le fichier audio et renvoie le chemin local."""
        raise NotImplementedError


class DirectUrlSource(AudioSource):
    async def download(self, url: str, dest_dir: Path, max_size: int, progress_cb=None) -> Path:
        import httpx

        ok, msg = validate_url(url)
        if not ok:
            raise ValueError(msg)

        dest_dir.mkdir(parents=True, exist_ok=True)
        timeout = httpx.Timeout(30.0, connect=10.0)
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            # HEAD pour vérifier le type et la taille
            try:
                head = await client.head(url)
            except Exception:
                head = None
            content_type = ""
            content_length = None
            if head is not None:
                content_type = head.headers.get("content-type", "").split(";")[0].strip().lower()
                cl = head.headers.get("content-length")
                if cl and cl.isdigit():
                    content_length = int(cl)
            if content_type and content_type not in ("audio/mpeg", "audio/mp3", "application/octet-stream"):
                # on accepte octet-stream si extension .mp3
                if not url.lower().endswith(".mp3"):
                    raise ValueError(f"Format non supporté : {content_type}")
            if content_length is not None and content_length > max_size:
                raise ValueError("Fichier trop gros")

            # Nom de fichier depuis l'URL
            name = os.path.basename(urlparse(url).path) or "import.mp3"
            if not name.lower().endswith(".mp3"):
                # ajoute .mp3 si pas d'extension audio reconnue
                if "." in name:
                    name = name.rsplit(".", 1)[0] + ".mp3"
                else:
                    name = name + ".mp3"
            dest = dest_dir / name
            # éviter écrasement
            i = 1
            base = dest.stem
            while dest.exists():
                dest = dest_dir / f"{base}_{i}.mp3"
                i += 1

            total = content_length or 0
            downloaded = 0
            async with client.stream("GET", url) as resp:
                resp.raise_for_status()
                ct = resp.headers.get("content-type", "").split(";")[0].strip().lower()
                if ct and ct not in ("audio/mpeg", "audio/mp3", "application/octet-stream"):
                    if not url.lower().endswith(".mp3"):
                        raise ValueError(f"Format non supporté : {ct}")
                cl = resp.headers.get("content-length")
                if cl and cl.isdigit():
                    total = int(cl)
                    if total > max_size:
                        raise ValueError("Fichier trop gros")
                with open(dest, "wb") as f:
                    async for chunk in resp.aiter_bytes(chunk_size=65536):
                        f.write(chunk)
                        downloaded += len(chunk)
                        if downloaded > max_size:
                            f.close()
                            try:
                                dest.unlink()
                            except Exception:
                                pass
                            raise ValueError("Fichier trop gros")
                        if progress_cb is not None:
                            progress_cb(downloaded, total)
            return dest
        # unreachable
        raise RuntimeError("download failed")
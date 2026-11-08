"""Parsing des métadonnées : tags ID3 + nom de fichier."""
from __future__ import annotations

import hashlib
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from mutagen.mp3 import MP3
from mutagen.id3 import ID3, ID3NoHeaderError

# Motifs configurables pour le nom de fichier.
# Chaque motif est une regex avec groupes nommés artist/title/tracknum (optionnels).
DEFAULT_PATTERNS = [
    # 01 - Artiste - Titre.mp3
    r"^(?P<tracknum>\d+)\s*-\s*(?P<artist>.+?)\s*-\s*(?P<title>.+)$",
    # Artiste - Titre.mp3
    r"^(?P<artist>.+?)\s*-\s*(?P<title>.+)$",
    # Artiste-Titre.mp3
    r"^(?P<artist>.+?)\s*-\s*(?P<title>.+)$",  # doublon volontaire pour compat
    r"^(?P<artist>[^-]+?)-(?P<title>[^-]+)$",
]


def _clean(s: Optional[str]) -> Optional[str]:
    if s is None:
        return None
    s = s.strip()
    return s or None


def parse_filename(name: str, patterns: Optional[list[str]] = None) -> dict:
    """Parse un nom de fichier et renvoie {artist, title, tracknum} (valeurs None si non trouvées)."""
    base = os.path.splitext(os.path.basename(name))[0]
    base = base.strip()
    patterns = patterns or DEFAULT_PATTERNS
    for pat in patterns:
        m = re.match(pat, base)
        if m:
            gd = m.groupdict()
            return {
                "artist": _clean(gd.get("artist")),
                "title": _clean(gd.get("title")),
                "tracknum": _clean(gd.get("tracknum")),
            }
    # Repli : titre = nom de fichier
    return {"artist": None, "title": _clean(base), "tracknum": None}


def read_id3(path: str | Path) -> dict:
    """Lit les tags ID3 (et la durée). Renvoie dict avec clés title/artist/album/duration/cover_bytes."""
    path = str(path)
    result = {"title": None, "artist": None, "album": None, "duration": None, "cover_bytes": None, "cover_ext": None}
    try:
        audio = MP3(path)
        result["duration"] = float(audio.info.length) if audio.info else None
    except Exception:
        pass
    try:
        tags = ID3(path)
    except ID3NoHeaderError:
        tags = None
    except Exception:
        tags = None
    if tags is not None:
        def get(frame_ids):
            for fid in frame_ids:
                f = tags.get(fid)
                if f is not None:
                    try:
                        return str(f.text[0]) if hasattr(f, "text") else str(f)
                    except Exception:
                        try:
                            return str(f)
                        except Exception:
                            return None
            return None

        result["title"] = _clean(get(["TIT2"]))
        result["artist"] = _clean(get(["TPE1"]))
        result["album"] = _clean(get(["TALB"]))
        # pochette
        for key in tags.keys():
            if key.startswith("APIC"):
                apic = tags[key]
                result["cover_bytes"] = apic.data
                result["cover_ext"] = apic.mime.split("/")[-1] if apic.mime else "jpg"
                break
    return result


def write_tags(path: str | Path, title: Optional[str], artist: Optional[str], album: Optional[str]) -> None:
    """Écrit les tags ID3 (optionnel)."""
    from mutagen.id3 import ID3, TIT2, TPE1, TALB, ID3NoHeaderError
    try:
        tags = ID3(path)
    except ID3NoHeaderError:
        tags = ID3()
    if title is not None:
        tags["TIT2"] = TIT2(encoding=3, text=title)
    if artist is not None:
        tags["TPE1"] = TPE1(encoding=3, text=artist)
    if album is not None:
        tags["TALB"] = TALB(encoding=3, text=album)
    tags.save(path)


def file_hash(path: str | Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


@dataclass
class MetadataResult:
    title: Optional[str]
    artist: Optional[str]
    album: Optional[str]
    duration: Optional[float]
    cover_bytes: Optional[bytes]
    cover_ext: Optional[str]
    source: str  # 'id3' | 'filename' | 'manual'


def build_metadata(path: str | Path, patterns: Optional[list[str]] = None) -> MetadataResult:
    """Priorité : tags ID3, puis nom de fichier, puis None (saisie manuelle)."""
    if patterns is None:
        try:
            from ..config import get_config
            patterns = get_config().filename_patterns
        except Exception:
            patterns = None
    id3 = read_id3(path)
    parsed = parse_filename(str(path), patterns)
    title = id3["title"] or parsed["title"]
    artist = id3["artist"] or parsed["artist"]
    album = id3["album"]
    source = "id3" if (id3["title"] or id3["artist"]) else ("filename" if (parsed["title"] or parsed["artist"]) else "manual")
    return MetadataResult(
        title=title,
        artist=artist,
        album=album,
        duration=id3["duration"],
        cover_bytes=id3["cover_bytes"],
        cover_ext=id3["cover_ext"],
        source=source,
    )
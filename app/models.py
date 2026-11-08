"""Modèles de données (dataclasses simples)."""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Optional


@dataclass
class Track:
    id: Optional[int] = None
    path: str = ""
    title: Optional[str] = None
    artist: Optional[str] = None
    album: Optional[str] = None
    duration: Optional[float] = None
    cover_path: Optional[str] = None
    added_at: Optional[str] = None
    file_hash: Optional[str] = None

    @classmethod
    def from_row(cls, row) -> "Track":
        return cls(
            id=row["id"],
            path=row["path"],
            title=row["title"],
            artist=row["artist"],
            album=row["album"],
            duration=row["duration"],
            cover_path=row["cover_path"],
            added_at=row["added_at"],
            file_hash=row["file_hash"],
        )

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Playlist:
    id: Optional[int] = None
    name: str = ""
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    @classmethod
    def from_row(cls, row) -> "Playlist":
        return cls(
            id=row["id"],
            name=row["name"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
"""Configuration de l'application (env + fichier optionnel)."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


def _env(key: str, default: str) -> str:
    return os.environ.get(key, default)


@dataclass
class Config:
    media_dir: Path = field(default_factory=lambda: Path(_env("MEDIA_DIR", "media")).resolve())
    db_path: Path = field(default_factory=lambda: Path(_env("DB_PATH", "data/playlistinator.db")).resolve())
    host: str = field(default_factory=lambda: _env("HOST", "127.0.0.1"))
    port: int = field(default_factory=lambda: int(_env("PORT", "8000")))
    max_import_size: int = field(default_factory=lambda: int(_env("MAX_IMPORT_SIZE", str(50 * 1024 * 1024))))
    user_agent: str = field(default_factory=lambda: _env(
        "USER_AGENT", "Playlistinator/1.0 (personal local music player)"))
    cover_search_enabled: bool = True
    filename_patterns: list[str] | None = field(default_factory=lambda: (
        [p.strip() for p in os.environ.get("FILENAME_PATTERNS", "").split(";") if p.strip()] or None
    ))

    def ensure_dirs(self) -> None:
        self.media_dir.mkdir(parents=True, exist_ok=True)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)


_config: Config | None = None


def get_config() -> Config:
    global _config
    if _config is None:
        _config = Config()
        _config.ensure_dirs()
    return _config


def reset_config(cfg: Config | None = None) -> None:
    global _config
    _config = cfg
    if _config is not None:
        _config.ensure_dirs()
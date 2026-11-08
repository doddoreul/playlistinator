"""Point d'entrée : python -m app"""
from __future__ import annotations

import uvicorn

from .config import get_config

cfg = get_config()
print(f"Playlistinator starting on http://{cfg.host}:{cfg.port}")
uvicorn.run("app:app", host=cfg.host, port=cfg.port, reload=False)
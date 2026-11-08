"""Application FastAPI Playlistinator."""
from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .config import get_config
from .database import init_db

cfg = get_config()
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

templates = Jinja2Templates(directory="app/templates")

app = FastAPI(title="Playlistinator", version="1.0.0")

# statiques
app.mount("/static", StaticFiles(directory="app/static"), name="static")
from .config import get_config as _gc
_mc = _gc().media_dir
app.mount("/media", StaticFiles(directory=str(_mc)), name="media")

# routes
from .routes import library, playlists, import_url, covers, stream, gestion  # noqa: E402

app.include_router(library.router)
app.include_router(playlists.router)
app.include_router(import_url.router)
app.include_router(covers.router)
app.include_router(stream.router)
app.include_router(gestion.router)

# plugins
from .plugins.loader import load_plugins
load_plugins(app)

@app.on_event("startup")
def on_startup():
    init_db()
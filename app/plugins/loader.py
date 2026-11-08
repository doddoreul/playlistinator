"""Chargeur de plugins : scanne un dossier et appelle register(app, context)."""
from __future__ import annotations

import importlib.util
import logging
import os
import sys
from pathlib import Path
from typing import Any

from ..config import get_config

log = logging.getLogger("playlistinator.plugins")

_loaded: list[str] = []
_import_tabs: list[dict] = []


def _plugins_dir() -> Path:
    env = os.environ.get("PLUGINS_DIR")
    if env:
        return Path(env).resolve()
    return Path("plugins").resolve()


def register_import_tab(tab: dict) -> None:
    _import_tabs.append(tab)


def import_tabs() -> list[dict]:
    return list(_import_tabs)


def build_context(app: Any) -> dict[str, Any]:
    from .. import templates
    from ..database import conn_ctx, get_conn, init_db
    from ..services import audio_source, covers, importer, metadata, scanner
    return {
        "app": app,
        "config": get_config(),
        "templates": templates,
        "db": {"conn_ctx": conn_ctx, "get_conn": get_conn, "init_db": init_db},
        "services": {
            "audio_source": audio_source,
            "covers": covers,
            "importer": importer,
            "metadata": metadata,
            "scanner": scanner,
        },
        "register_import_tab": register_import_tab,
    }


def _register_module(mod, app, context, name):
    reg = getattr(mod, "register", None)
    if callable(reg):
        try:
            reg(app, context)
            _loaded.append(name)
            log.info("Plugin chargé : %s", name)
        except Exception:
            log.exception("Erreur chargement plugin %s", name)
    else:
        log.warning("Plugin %s : pas de fonction register(app, context)", name)


def load_plugins(app: Any) -> list[str]:
    pdir = _plugins_dir()
    if not pdir.exists():
        pdir.mkdir(parents=True, exist_ok=True)
        return []
    # ajoute la racine au path pour imports relatifs des plugins
    root = str(Path.cwd())
    if root not in sys.path:
        sys.path.insert(0, root)
    # plugins sous forme de fichiers .py
    for f in sorted(pdir.glob("*.py")):
        if f.name.startswith("_"):
            continue
        name = f.stem
        try:
            spec = importlib.util.spec_from_file_location(f"plugin_{name}", f)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            _register_module(mod, app, build_context(app), name)
        except Exception:
            log.exception("Erreur import plugin fichier %s", f)
    # plugins sous forme de dossiers avec plugin.py ou __init__.py
    for d in sorted(pdir.iterdir()):
        if not d.is_dir() or d.name.startswith("_") or d.name.startswith("."):
            continue
        entry = d / "plugin.py"
        if not entry.exists():
            entry = d / "__init__.py"
        if not entry.exists():
            continue
        name = d.name
        try:
            spec = importlib.util.spec_from_file_location(f"plugin_{name}", entry, submodule_search_locations=[str(d)])
            mod = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = mod
            spec.loader.exec_module(mod)
            _register_module(mod, app, build_context(app), name)
        except Exception:
            log.exception("Erreur import plugin dossier %s", d)
    return list(_loaded)


def loaded_plugins() -> list[str]:
    return list(_loaded)
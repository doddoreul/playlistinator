"""Chargeur de plugins : scanne un dossier et appelle register(app, context)."""
from __future__ import annotations

import importlib.util
import logging
import os
import shutil
import sys
from pathlib import Path
from typing import Any

from ..config import get_config

log = logging.getLogger("playlistinator.plugins")

_loaded: list[str] = []
_import_tabs: list[dict] = []
_app: Any = None


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


def _load_one(name: str, path: Path, app: Any) -> bool:
    root = str(Path.cwd())
    if root not in sys.path:
        sys.path.insert(0, root)
    entry = path / "plugin.py"
    if not entry.exists():
        entry = path / "__init__.py"
    if not entry.exists():
        # fichier .py direct
        if path.suffix == ".py":
            entry = path
        else:
            return False
    try:
        if entry.is_dir():
            return False
        spec = importlib.util.spec_from_file_location(f"plugin_{name}", entry, submodule_search_locations=[str(path)] if path.is_dir() else None)
        mod = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = mod
        spec.loader.exec_module(mod)
        _register_module(mod, app, build_context(app), name)
        return True
    except Exception:
        log.exception("Erreur import plugin %s", name)
        return False


def load_plugins(app: Any) -> list[str]:
    global _app
    _app = app
    pdir = _plugins_dir()
    if not pdir.exists():
        pdir.mkdir(parents=True, exist_ok=True)
        return []
    root = str(Path.cwd())
    if root not in sys.path:
        sys.path.insert(0, root)
    # fichiers .py
    for f in sorted(pdir.glob("*.py")):
        if f.name.startswith("_"):
            continue
        _load_one(f.stem, f, app)
    # dossiers
    for d in sorted(pdir.iterdir()):
        if not d.is_dir() or d.name.startswith("_") or d.name.startswith("."):
            continue
        _load_one(d.name, d, app)
    return list(_loaded)


def loaded_plugins() -> list[str]:
    return list(_loaded)


def _plugins_root() -> Path:
    return Path("plugins").resolve()


def _available_root() -> Path:
    return Path("plugins_available").resolve()


def discover_plugins() -> list[dict]:
    """Liste les plugins trouvés (actifs et disponibles)."""
    active_dir = _plugins_root()
    avail_dir = _available_root()
    names = set()
    for d in (active_dir, avail_dir):
        if d.exists():
            for sub in d.iterdir():
                if sub.is_dir() and not sub.name.startswith(("_", ".")):
                    names.add(sub.name)
    result = []
    for name in sorted(names):
        active = (active_dir / name).exists()
        loaded = name in _loaded
        result.append({"name": name, "active": active, "loaded": loaded})
    return result


def activate_plugin(name: str) -> tuple[bool, str]:
    avail = _available_root() / name
    active = _plugins_root() / name
    if active.exists():
        return False, "déjà actif"
    if not avail.exists():
        return False, "plugin introuvable"
    try:
        active.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(avail), str(active))
    except Exception as e:
        return False, str(e)
    # chargement dynamique
    if _app is not None:
        ok = _load_one(name, active, _app)
        if ok:
            return True, "activé"
        return True, "activé (chargement manuel requis)"
    return True, "activé (redémarrer pour charger les routes)"


def deactivate_plugin(name: str) -> tuple[bool, str]:
    active = _plugins_root() / name
    avail = _available_root() / name
    if not active.exists():
        return False, "pas actif"
    try:
        avail.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(active), str(avail))
    except Exception as e:
        return False, str(e)
    return True, "désactivé (redémarrer pour appliquer)"
import sys, os, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

tmp = tempfile.mkdtemp()
plugin_dir = os.path.join(tmp, "plugins")
os.makedirs(os.path.join(plugin_dir, "demo"), exist_ok=True)
with open(os.path.join(plugin_dir, "demo", "plugin.py"), "w") as f:
    f.write("def register(app, context):\n    app.state.demo_loaded = True\n")
os.environ["PLUGINS_DIR"] = plugin_dir
os.environ.setdefault("MEDIA_DIR", os.path.join(tmp, "media"))
os.environ.setdefault("DB_PATH", os.path.join(tmp, "t.db"))
os.makedirs(os.environ["MEDIA_DIR"], exist_ok=True)

from fastapi import FastAPI
from app.plugins.loader import load_plugins

def test_plugin_loader():
    app = FastAPI()
    loaded = load_plugins(app)
    assert "demo" in loaded
    assert getattr(app.state, "demo_loaded", False) is True
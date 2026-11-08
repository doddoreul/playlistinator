import sys, os, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

tmp = tempfile.mkdtemp()
os.environ["MEDIA_DIR"] = os.path.join(tmp, "media")
os.environ["DB_PATH"] = os.path.join(tmp, "test.db")
os.makedirs(os.environ["MEDIA_DIR"], exist_ok=True)

from app.config import Config, reset_config
cfg = Config(media_dir=__import__("pathlib").Path(os.environ["MEDIA_DIR"]),
             db_path=__import__("pathlib").Path(os.environ["DB_PATH"]))
reset_config(cfg)
from app.database import init_db
init_db()

from app.database import conn_ctx
with conn_ctx() as c:
    c.execute("INSERT INTO tracks (path, title, artist, file_hash) VALUES (?,?,?,?)",
              ("/tmp/x.mp3", "Titre", "Artiste", "hx"))
    tid = c.execute("SELECT id FROM tracks WHERE file_hash='hx'").fetchone()[0]

from fastapi.testclient import TestClient
from app import app as fastapi_app
client = TestClient(fastapi_app)

def test_create_playlist_add_reorder():
    r = client.post("/api/playlists", data={"name": "MaListe"})
    assert r.status_code == 200
    pid = r.json()["id"]
    r = client.post(f"/api/playlists/{pid}/tracks", data={"track_ids": str(tid)})
    assert r.status_code == 200
    r = client.get(f"/api/playlists/{pid}/tracks")
    assert r.status_code == 200
    # reorder (single)
    r = client.post(f"/api/playlists/{pid}/reorder", data={"order": str(tid)})
    assert r.status_code == 200
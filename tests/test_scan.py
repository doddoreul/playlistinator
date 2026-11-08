import sys, os, tempfile, subprocess
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

tmp = tempfile.mkdtemp()
media = os.path.join(tmp, "media")
os.makedirs(media, exist_ok=True)
os.environ["MEDIA_DIR"] = media
os.environ["DB_PATH"] = os.path.join(tmp, "test.db")

# generate a small mp3
mp3_path = os.path.join(media, "Daft Punk - Harder Better.mp3")
subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono", "-t", "1", "-q:a", "9", mp3_path],
               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

from app.config import Config, reset_config
cfg = Config(media_dir=__import__("pathlib").Path(media), db_path=__import__("pathlib").Path(os.environ["DB_PATH"]))
reset_config(cfg)
from app.database import init_db
init_db()
from app.services.scanner import scan_media
res = scan_media()
assert res["added"] == 1, res

from app.database import conn_ctx
with conn_ctx() as c:
    row = c.execute("SELECT title, artist FROM tracks").fetchone()
assert row["title"] == "Harder Better"
assert row["artist"] == "Daft Punk"
import sys, os, tempfile, subprocess
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

tmp = tempfile.mkdtemp()
media = os.path.join(tmp, "media")
os.makedirs(media, exist_ok=True)
os.environ["MEDIA_DIR"] = media
os.environ["DB_PATH"] = os.path.join(tmp, "test.db")

mp3_path = os.path.join(media, "01 - Unknown - Unknown.mp3")
subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono", "-t", "1", "-q:a", "9", mp3_path],
               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

from mutagen.id3 import ID3, TIT2, TPE1, TALB
from mutagen.mp3 import MP3
audio = MP3(mp3_path)
try:
    audio.add_tags()
except Exception:
    pass
audio.tags["TIT2"] = TIT2(encoding=3, text="Real Title")
audio.tags["TPE1"] = TPE1(encoding=3, text="Real Artist")
audio.tags["TALB"] = TALB(encoding=3, text="Real Album")
audio.save()

from app.config import Config, reset_config
cfg = Config(media_dir=__import__("pathlib").Path(media), db_path=__import__("pathlib").Path(os.environ["DB_PATH"]))
reset_config(cfg)
from app.database import init_db
init_db()
from app.services.scanner import scan_media
scan_media()

from app.database import conn_ctx
with conn_ctx() as c:
    row = c.execute("SELECT title, artist, album FROM tracks").fetchone()
assert row["title"] == "Real Title"
assert row["artist"] == "Real Artist"
assert row["album"] == "Real Album"
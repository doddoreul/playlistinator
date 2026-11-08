import sys, os, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# configure temp db before importing app
tmp = tempfile.mkdtemp()
os.environ["MEDIA_DIR"] = os.path.join(tmp, "media")
os.environ["DB_PATH"] = os.path.join(tmp, "test.db")
os.makedirs(os.environ["MEDIA_DIR"], exist_ok=True)

from app.config import reset_config, get_config
from app.config import Config
cfg = Config(media_dir=__import__("pathlib").Path(os.environ["MEDIA_DIR"]),
             db_path=__import__("pathlib").Path(os.environ["DB_PATH"]))
reset_config(cfg)
from app.database import init_db
init_db()

from app.database import conn_ctx

# insert a track
with conn_ctx() as c:
    c.execute("INSERT INTO tracks (path, title, artist, file_hash) VALUES (?,?,?,?)",
              ("/tmp/a.mp3", "T1", "A", "h1"))
    c.execute("INSERT INTO tracks (path, title, artist, file_hash) VALUES (?,?,?,?)",
              ("/tmp/b.mp3", "T2", "A", "h2"))
    tid1 = c.execute("SELECT id FROM tracks WHERE file_hash='h1'").fetchone()[0]
    tid2 = c.execute("SELECT id FROM tracks WHERE file_hash='h2'").fetchone()[0]
    c.execute("INSERT INTO playlists (name) VALUES (?)", ("P1",))
    pid = c.execute("SELECT last_insert_rowid()").fetchone()[0]

# add tracks
from app.routes.playlists import add_tracks, reorder, remove_track
add_tracks(pid, f"{tid1},{tid2}")
# dedup: adding again should not duplicate
add_tracks(pid, f"{tid1}")
with conn_ctx() as c:
    cnt = c.execute("SELECT COUNT(*) AS n FROM playlist_tracks WHERE playlist_id=?", (pid,)).fetchone()[0]
assert cnt == 2, cnt

# reorder
reorder(pid, f"{tid2},{tid1}")
with conn_ctx() as c:
    rows = c.execute("SELECT track_id FROM playlist_tracks WHERE playlist_id=? ORDER BY position", (pid,)).fetchall()
assert [r[0] for r in rows] == [tid2, tid1]

# remove
remove_track(pid, tid2)
with conn_ctx() as c:
    rows = c.execute("SELECT track_id FROM playlist_tracks WHERE playlist_id=? ORDER BY position", (pid,)).fetchall()
assert [r[0] for r in rows] == [tid1]
with conn_ctx() as c:
    pos = c.execute("SELECT position FROM playlist_tracks WHERE playlist_id=? AND track_id=?", (pid, tid1)).fetchone()[0]
assert pos == 1
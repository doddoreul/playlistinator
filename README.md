# Playlistinator

Personal, 100% local web music player (Spotify Web style), managing playlists from MP3 files stored on the user's machine.

## Stack

- **Server**: Python 3.11+ / FastAPI (chosen for simplicity, mutagen for ID3 tags, sqlite3 in stdlib, automatic OpenAPI docs).
- **Frontend**: HTML/CSS/JS served by the server, HTMX for interactions, vanilla JS for the player.
- **Database**: SQLite (`data/playlistinator.db`).
- **No cloud dependency.**

## Installation

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux/macOS
source .venv/bin/activate

pip install -r requirements.txt
```

## Launch

```bash
python -m app
```

Then open http://127.0.0.1:8000 in your browser.

## Configuration

Environment variables (all optional):

| Variable | Default | Description |
|---|---|---|
| `MEDIA_DIR` | `media` | Folder containing MP3s |
| `DB_PATH` | `data/playlistinator.db` | SQLite file |
| `HOST` | `127.0.0.1` | Listen address |
| `PORT` | `8000` | Port |
| `MAX_IMPORT_SIZE` | `52428800` (50 MB) | Max import size |
| `USER_AGENT` | `Playlistinator/1.0 (...)` | User-Agent (MusicBrainz) |
| `FILENAME_PATTERNS` | (default patterns) | Semicolon-separated patterns to parse filenames |
| `PLUGINS_DIR` | `plugins` | Plugins folder |

## Usage

1. Drop MP3s into `media/`, then click "Scan".
2. Create playlists in the sidebar, add tracks.
3. Play a playlist, navigate with keyboard shortcuts (space, arrows, N/P).
4. Import a track by direct URL via the "Import" page.
5. Search for a cover via the "Details" button of a track.

## Plugins

Extensible plugin system. Each plugin is a folder in `plugins/` containing a `plugin.py` (or `__init__.py`) exposing `register(app, context)`. See `plugins/README.md` and `plugins/example/`. Location configurable via `PLUGINS_DIR`.

Optional plugins (e.g. YouTube) are provided in `plugins_available/`. To enable, copy the folder into `plugins/` (or point `PLUGINS_DIR` at it).

## Tests

```bash
python -m pytest
```

## Known limitations

- Cover search depends on MusicBrainz/Cover Art Archive (network, 1 req/s rate limit).
- No multi-device sync (personal local use).
- No advanced playback (crossfade, etc.).
- Tag editing writes to the file (mutagen); library refresh is manual.
- No authentication (local use only).
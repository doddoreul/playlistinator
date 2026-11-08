# Plugins Playlistinator

Each plugin is a folder in `plugins/` containing a `plugin.py` (or `__init__.py`), or a `.py` file directly in `plugins/`.

## Minimal interface

```python
def register(app, context):
    # context contains: app, config, templates, db, services
    ...
```

## Provided context

- `context["app"]`: FastAPI instance
- `context["config"]`: configuration
- `context["templates"]`: Jinja2Templates
- `context["db"]`: conn_ctx, get_conn, init_db
- `context["services"]`: audio_source, covers, importer, metadata, scanner

## Import rule

Any file imported by a plugin must be placed in `context["config"].media_dir`
(same folder as a normal import), then indexed via `context["services"]["scanner"].index_file(path)`.

## Custom folder

Set `PLUGINS_DIR=/path/to/plugins` to change the location.

## Available (not shipped by default)

Optional plugins (e.g. YouTube) are provided in `plugins_available/`.
To enable, copy the folder into `plugins/` (or point `PLUGINS_DIR` at it).

## Example

See `plugins/example/`. Exposed route: `GET /plugins/example/hello`.
# Plugins Playlistinator

Chaque plugin est un dossier dans `plugins/` contenant un fichier `plugin.py`
(ou `__init__.py`), ou un fichier `.py` directement dans `plugins/`.

## Interface minimale

```python
def register(app, context):
    # context contient : app, config, templates, db, services
    ...
```

## Règle d'import

Tout fichier importé par un plugin doit être placé dans `context["config"].media_dir`
(le même dossier que pour un import normal), puis indexé via `context["services"]["scanner"].index_file(path)`.

## Contexte fourni

- `context["app"]` : instance FastAPI
- `context["config"]` : configuration
- `context["templates"]` : Jinja2Templates
- `context["db"]` : conn_ctx, get_conn, init_db
- `context["services"]` : audio_source, covers, importer, metadata, scanner

## Dossier personnalisé

Définir `PLUGINS_DIR=/chemin/vers/plugins` pour changer l'emplacement.

## Plugins disponibles (non livrés par défaut)

Des plugins optionnels (ex. YouTube) sont fournis dans `plugins_available/`.
Pour les activer, copier le dossier dans `plugins/` (ou pointer `PLUGINS_DIR` dessus).

## Exemple

Voir `plugins/example/`. Route exposée : `GET /plugins/example/hello`.
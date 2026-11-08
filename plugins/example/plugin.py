"""Exemple de plugin Playlistinator.

Un plugin est un module Python exposant une fonction register(app, context).
Il peut ajouter des routes, des services, etc.
"""


def register(app, context):
    from fastapi import APIRouter
    from fastapi.responses import JSONResponse

    router = APIRouter()

    @router.get("/hello")
    def hello():
        cfg = context["config"]
        return JSONResponse({"message": "Bonjour depuis le plugin example", "media_dir": str(cfg.media_dir)})

    app.include_router(router, prefix="/plugins/example", tags=["example"])
"""Startpunkt: `uvicorn app.main:app`. Liefert API und die PWA (Ordner web/) aus."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from . import __version__
from .api import router
from .config import Einstellungen, einstellungen
from .mealie_client import MealieClient
from .speicher import Speicher

WEB_ORDNER = Path(__file__).resolve().parent.parent / "web"


def create_app(einst: Einstellungen | None = None, mealie: MealieClient | None = None) -> FastAPI:
    einst = einst or einstellungen()
    app = FastAPI(title="Rührwerk", version=__version__, docs_url="/api/docs", openapi_url="/api/openapi.json")
    app.state.einstellungen = einst
    app.state.mealie = mealie or MealieClient(einst.mealie_basis, einst.mealie_token)
    app.state.speicher = Speicher(einst.data_dir)
    app.include_router(router)
    if WEB_ORDNER.is_dir():
        app.mount("/", StaticFiles(directory=WEB_ORDNER, html=True), name="web")
    return app


app = create_app()

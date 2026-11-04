"""HTTP-Schnittstelle (FastAPI). Spricht mit Mealie nur über MealieClient."""

from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Path, Query, Request, Response
from pydantic import BaseModel, Field, field_validator

from . import __version__
from .mealie_client import MealieClient, MealieFehler
from .rezept import aufbereiten
from .speicher import Speicher

router = APIRouter(prefix="/api")

# Nur diese Zeichen sind in Slugs erlaubt – verhindert Pfad-Tricks wie "../users/self"
Slug = Annotated[str, Path(pattern=r"^[A-Za-z0-9_-]{1,200}$")]
RezeptId = Annotated[str, Path(pattern=r"^[0-9a-fA-F-]{36}$")]
BILD_DATEIEN = {"original.webp", "min-original.webp", "tiny-original.webp"}


def _mealie(request: Request) -> MealieClient:
    return request.app.state.mealie


def _speicher(request: Request) -> Speicher:
    return request.app.state.speicher


async def _mealie_aufruf(coro):
    try:
        return await coro
    except MealieFehler as exc:
        text = str(exc)
        code = 404 if "404" in text else 502
        raise HTTPException(status_code=code, detail=text) from exc


class ImportAnfrage(BaseModel):
    url: str = Field(max_length=2000)

    @field_validator("url")
    @classmethod
    def nur_web_adressen(cls, v: str) -> str:
        v = v.strip()
        if not v.lower().startswith(("http://", "https://")):
            raise ValueError("Bitte einen Link angeben, der mit http:// oder https:// beginnt.")
        return v


class Werte(BaseModel):
    dauer_s: float | None = Field(default=None, ge=0, le=86400)
    temperatur_c: float | None = Field(default=None, ge=0, le=250)
    varoma: bool = False
    stufe: float | None = Field(default=None, ge=0, le=10)
    art: Literal["stufe", "sanftruehr", "teigknet", "turbo", "keine"] = "keine"
    linkslauf: bool = False
    wiederholungen: int = Field(default=1, ge=1, le=99)


class BestaetigungsAnfrage(BaseModel):
    werte: Werte


@router.get("/status")
async def status(request: Request):
    einst = request.app.state.einstellungen
    return {"version": __version__, "mealie_url": einst.mealie_basis, "token_gesetzt": bool(einst.mealie_token)}


@router.post("/verbindung-testen")
async def verbindung_testen(request: Request):
    return await _mealie_aufruf(_mealie(request).verbindung_testen())


@router.post("/import", status_code=201)
async def rezept_importieren(daten: ImportAnfrage, request: Request):
    slug = await _mealie_aufruf(_mealie(request).rezept_importieren(daten.url))
    return {"slug": slug}


@router.get("/rezepte")
async def rezepte(request: Request, suche: str = Query("", max_length=100), seite: int = Query(1, ge=1, le=1000)):
    roh = await _mealie_aufruf(_mealie(request).rezepte_suchen(suche, seite))
    return {
        "gesamt": roh.get("total", 0),
        "seite": roh.get("page", seite),
        "seiten": roh.get("total_pages", 1),
        "rezepte": [
            {"id": r.get("id"), "slug": r.get("slug"), "name": r.get("name"), "hat_bild": bool(r.get("image"))}
            for r in roh.get("items", [])
        ],
    }


@router.get("/rezepte/{slug}")
async def rezept(slug: Slug, request: Request):
    roh = await _mealie_aufruf(_mealie(request).rezept_laden(slug))
    return aufbereiten(roh, _speicher(request).laden(slug))


@router.put("/rezepte/{slug}/schritte/{schritt_id}/einstellungen/{nr}")
async def bestaetigen(slug: Slug, schritt_id: Slug, nr: Annotated[int, Path(ge=0, le=99)], daten: BestaetigungsAnfrage, request: Request):
    """Der Nutzer bestätigt (oder korrigiert) eine erkannte Einstellung per Tippen."""
    roh = await _mealie_aufruf(_mealie(request).rezept_laden(slug))
    rezept_ = aufbereiten(roh)
    schritt = next((s for s in rezept_["schritte"] if s["id"] == schritt_id), None)
    if schritt is None or nr >= len(schritt["einstellungen"]):
        raise HTTPException(status_code=404, detail="Diese Einstellung gibt es im Rezept nicht (mehr).")
    quelle = schritt["einstellungen"][nr]["text"]
    _speicher(request).bestaetigen(slug, schritt_id, nr, quelle, daten.werte.model_dump())
    return {"status": "bestaetigt"}


@router.delete("/rezepte/{slug}/schritte/{schritt_id}/einstellungen/{nr}", status_code=204)
async def zuruecknehmen(slug: Slug, schritt_id: Slug, nr: Annotated[int, Path(ge=0, le=99)], request: Request):
    _speicher(request).zuruecknehmen(slug, schritt_id, nr)
    return Response(status_code=204)


@router.get("/bild/{rezept_id}")
async def bild(rezept_id: RezeptId, request: Request, datei: str = Query("min-original.webp")):
    """Reicht das Rezeptbild von Mealie durch, damit der Token nie im Browser landet."""
    if datei not in BILD_DATEIEN:
        raise HTTPException(status_code=400, detail="Unbekannte Bilddatei.")
    inhalt, typ = await _mealie_aufruf(_mealie(request).bild_laden(rezept_id, datei))
    return Response(content=inhalt, media_type=typ, headers={"Cache-Control": "private, max-age=86400"})

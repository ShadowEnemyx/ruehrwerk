"""Sehr kleiner Client für die offizielle Mealie-REST-API (Stand geprüft: Mealie v3.30.0).

Genutzte Endpunkte (im Mealie-Quellcode v3.30.0 geprüft):
  GET  /api/app/about              Version, ohne Anmeldung
  GET  /api/users/self             prüft, ob der Token gültig ist
  POST /api/recipes/create/url     Rezept per Link importieren, Antwort = Slug (Text)
  POST /api/recipes/create/ai      Rezept per KI aus Fotos/Text/Link (Formular: images, content, url), Antwort = Slug
  GET  /api/recipes                Rezeptliste (Parameter: search, page, perPage)
  GET  /api/recipes/{slug}         ein Rezept komplett
  GET  /api/media/recipes/{id}/images/{datei}   Rezeptbild
Anmeldung: Header "Authorization: Bearer <API-Token>".
"""

import httpx


def _mealie_meldung(antwort: httpx.Response) -> str:
    """Holt, falls vorhanden, den Fehlertext aus der Mealie-Antwort (Form: {"detail": {"message": ...}})."""
    try:
        detail = antwort.json().get("detail")
    except (ValueError, AttributeError):
        return ""
    if isinstance(detail, dict):
        detail = detail.get("message")
    return detail.strip()[:300] if isinstance(detail, str) else ""


class MealieFehler(Exception):
    """Fehler mit einer Meldung, die man dem Nutzer direkt zeigen kann."""


class MealieClient:
    def __init__(self, basis_url: str, token: str, *, transport: httpx.AsyncBaseTransport | None = None):
        self._basis = basis_url.rstrip("/")
        self._token = token
        self._transport = transport

    def _client(self) -> httpx.AsyncClient:
        headers = {"Authorization": f"Bearer {self._token}"} if self._token else {}
        return httpx.AsyncClient(
            base_url=self._basis, headers=headers, timeout=httpx.Timeout(60.0, connect=5.0), transport=self._transport
        )

    async def _anfrage(self, methode: str, pfad: str, *, fehlertext_zeigen: bool = False, **kwargs) -> httpx.Response:
        try:
            async with self._client() as c:
                antwort = await c.request(methode, pfad, **kwargs)
        except httpx.ConnectError as exc:
            raise MealieFehler(f"Mealie ist unter {self._basis} nicht erreichbar.") from exc
        except httpx.TimeoutException as exc:
            raise MealieFehler("Mealie antwortet nicht rechtzeitig.") from exc
        except httpx.HTTPError as exc:
            raise MealieFehler(f"Verbindung zu Mealie fehlgeschlagen: {exc}") from exc
        if antwort.status_code == 401:
            raise MealieFehler("Mealie lehnt den API-Token ab (401). Bitte Token prüfen.")
        if antwort.status_code == 404:
            raise MealieFehler("Nicht gefunden (404).")
        if antwort.status_code >= 400:
            if fehlertext_zeigen:
                meldung = _mealie_meldung(antwort)
                if meldung:
                    raise MealieFehler(f"Mealie meldet einen Fehler ({antwort.status_code}): {meldung}")
            raise MealieFehler(f"Mealie meldet einen Fehler ({antwort.status_code}).")
        return antwort

    async def verbindung_testen(self) -> dict:
        """Prüft Erreichbarkeit und Token. Wirft MealieFehler mit verständlicher Meldung."""
        about = (await self._anfrage("GET", "/api/app/about")).json()
        if not self._token:
            raise MealieFehler("Es ist noch kein API-Token eingetragen.")
        await self._anfrage("GET", "/api/users/self")
        return {"version": about.get("version"), "produktion": about.get("production")}

    async def rezept_importieren(self, url: str) -> str:
        """Lässt Mealie ein Rezept von einem Link importieren. Gibt den Slug des neuen Rezepts zurück."""
        antwort = await self._anfrage("POST", "/api/recipes/create/url", json={"url": url, "includeTags": False})
        slug = antwort.json()
        if not isinstance(slug, str) or not slug:
            raise MealieFehler("Mealie hat keinen Rezeptnamen zurückgegeben.")
        return slug

    async def rezept_per_ki(
        self, bilder: list[tuple[str, bytes, str]], text: str = "", url: str = ""
    ) -> str:
        """Lässt Mealie per KI ein Rezept aus Fotos (Dateiname, Inhalt, Medientyp), Text und/oder Link erstellen.

        Die KI braucht oft deutlich länger als ein normaler Import, daher ein großzügiges Zeitlimit.
        """
        felder = {k: v for k, v in (("content", text), ("url", url)) if v}
        dateien = [("images", (name, inhalt, typ)) for name, inhalt, typ in bilder]
        antwort = await self._anfrage(
            "POST", "/api/recipes/create/ai", data=felder, files=dateien or None,
            timeout=httpx.Timeout(240.0, connect=5.0), fehlertext_zeigen=True,
        )
        slug = antwort.json()
        if not isinstance(slug, str) or not slug:
            raise MealieFehler("Mealie hat keinen Rezeptnamen zurückgegeben.")
        return slug

    async def rezepte_suchen(self, suche: str = "", seite: int = 1, pro_seite: int = 30) -> dict:
        params = {"page": seite, "perPage": pro_seite, "orderBy": "name", "orderDirection": "asc"}
        if suche:
            params["search"] = suche
        return (await self._anfrage("GET", "/api/recipes", params=params)).json()

    async def rezept_laden(self, slug: str) -> dict:
        return (await self._anfrage("GET", f"/api/recipes/{slug}")).json()

    async def bild_laden(self, rezept_id: str, datei: str = "min-original.webp") -> tuple[bytes, str]:
        antwort = await self._anfrage("GET", f"/api/media/recipes/{rezept_id}/images/{datei}")
        return antwort.content, antwort.headers.get("content-type", "image/webp")

"""Tests für den Mealie-Client mit nachgestellten Antworten (kein echtes Mealie nötig)."""

import httpx
import pytest
import respx

from app.mealie_client import MealieClient, MealieFehler

pytestmark = pytest.mark.anyio

BASIS = "http://mealie.test"


@pytest.fixture
def client():
    return MealieClient(BASIS, "geheim-token")


@respx.mock
async def test_verbindung_ok(client):
    respx.get(f"{BASIS}/api/app/about").mock(return_value=httpx.Response(200, json={"version": "v3.30.0", "production": True}))
    selbst = respx.get(f"{BASIS}/api/users/self").mock(return_value=httpx.Response(200, json={"id": "x"}))
    info = await client.verbindung_testen()
    assert info["version"] == "v3.30.0"
    assert selbst.calls.last.request.headers["authorization"] == "Bearer geheim-token"


@respx.mock
async def test_token_abgelehnt(client):
    respx.get(f"{BASIS}/api/app/about").mock(return_value=httpx.Response(200, json={"version": "v3.30.0"}))
    respx.get(f"{BASIS}/api/users/self").mock(return_value=httpx.Response(401, json={"detail": "Unauthorized"}))
    with pytest.raises(MealieFehler, match="Token"):
        await client.verbindung_testen()


@respx.mock
async def test_ohne_token():
    respx.get(f"{BASIS}/api/app/about").mock(return_value=httpx.Response(200, json={"version": "v3.30.0"}))
    with pytest.raises(MealieFehler, match="noch kein API-Token"):
        await MealieClient(BASIS, "").verbindung_testen()


@respx.mock
async def test_nicht_erreichbar(client):
    respx.get(f"{BASIS}/api/app/about").mock(side_effect=httpx.ConnectError("boom"))
    with pytest.raises(MealieFehler, match="nicht erreichbar"):
        await client.verbindung_testen()


@respx.mock
async def test_import_gibt_slug(client):
    route = respx.post(f"{BASIS}/api/recipes/create/url").mock(return_value=httpx.Response(201, json="mein-rezept"))
    assert await client.rezept_importieren("https://example.org/rezept") == "mein-rezept"
    assert route.calls.last.request.read() == b'{"url":"https://example.org/rezept","includeTags":false}'


@respx.mock
async def test_import_fehler(client):
    respx.post(f"{BASIS}/api/recipes/create/url").mock(return_value=httpx.Response(400, json={"detail": {"message": "x"}}))
    with pytest.raises(MealieFehler, match="400"):
        await client.rezept_importieren("https://example.org/kaputt")


@respx.mock
async def test_rezept_laden_und_404(client):
    respx.get(f"{BASIS}/api/recipes/gibts").mock(return_value=httpx.Response(200, json={"slug": "gibts"}))
    respx.get(f"{BASIS}/api/recipes/gibtsnicht").mock(return_value=httpx.Response(404))
    assert (await client.rezept_laden("gibts"))["slug"] == "gibts"
    with pytest.raises(MealieFehler, match="404"):
        await client.rezept_laden("gibtsnicht")


@respx.mock
async def test_suche_parameter(client):
    route = respx.get(f"{BASIS}/api/recipes").mock(return_value=httpx.Response(200, json={"items": [], "total": 0}))
    await client.rezepte_suchen("suppe", seite=2)
    q = route.calls.last.request.url.params
    assert q["search"] == "suppe" and q["page"] == "2" and q["perPage"] == "30"

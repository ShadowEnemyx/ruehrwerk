"""Tests für die HTTP-Schnittstelle mit einem nachgestellten Mealie."""

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from app.config import Einstellungen
from app.main import create_app
from app.mealie_client import MealieClient
from tests.test_rezept import MEALIE_REZEPT

BASIS = "http://mealie.test"


@pytest.fixture
def app_client(tmp_path):
    einst = Einstellungen(mealie_url=BASIS, mealie_token="tok", data_dir=tmp_path / "daten")
    with respx.mock(assert_all_called=False) as mock:
        mock.get(f"{BASIS}/api/recipes/testsuppe").mock(return_value=httpx.Response(200, json=MEALIE_REZEPT))
        yield TestClient(create_app(einst, MealieClient(BASIS, "tok"))), mock


def test_status_zeigt_keinen_token(app_client):
    client, _ = app_client
    daten = client.get("/api/status").json()
    assert daten["token_gesetzt"] is True and "tok" not in str(daten.values())


def test_rezept_aufbereitet(app_client):
    client, _ = app_client
    r = client.get("/api/rezepte/testsuppe").json()
    assert r["name"] == "Testsuppe" and r["offen"] == 1


def test_bestaetigen_und_zuruecknehmen(app_client):
    client, _ = app_client
    url = "/api/rezepte/testsuppe/schritte/s3/einstellungen/0"
    antwort = client.put(url, json={"werte": {"dauer_s": 300, "temperatur_c": 100, "stufe": 1, "art": "stufe"}})
    assert antwort.status_code == 200
    r = client.get("/api/rezepte/testsuppe").json()
    e = r["schritte"][2]["einstellungen"][0]
    assert e["status"] == "bestaetigt" and e["stufe"] == 1 and r["offen"] == 0
    assert client.delete(url).status_code == 204
    assert client.get("/api/rezepte/testsuppe").json()["offen"] == 1


def test_bestaetigen_unbekannte_einstellung(app_client):
    client, _ = app_client
    antwort = client.put("/api/rezepte/testsuppe/schritte/s4/einstellungen/0", json={"werte": {}})
    assert antwort.status_code == 404


def test_bestaetigen_ungueltige_werte(app_client):
    client, _ = app_client
    antwort = client.put(
        "/api/rezepte/testsuppe/schritte/s3/einstellungen/0", json={"werte": {"stufe": 99, "art": "quatsch"}}
    )
    assert antwort.status_code == 422


def test_ungueltiger_slug_wird_abgelehnt(app_client):
    client, _ = app_client
    assert client.get("/api/rezepte/..%2Fusers%2Fself").status_code in (404, 422)
    assert client.get("/api/rezepte/a b").status_code == 422


def test_import_nur_web_adressen(app_client):
    client, mock = app_client
    mock.post(f"{BASIS}/api/recipes/create/url").mock(return_value=httpx.Response(201, json="neues-rezept"))
    assert client.post("/api/import", json={"url": "file:///etc/passwd"}).status_code == 422
    assert client.post("/api/import", json={"url": "javascript:alert(1)"}).status_code == 422
    ok = client.post("/api/import", json={"url": "https://example.org/rezept"})
    assert ok.status_code == 201 and ok.json() == {"slug": "neues-rezept"}


def test_mealie_nicht_erreichbar_gibt_klartext(app_client):
    client, mock = app_client
    mock.get(f"{BASIS}/api/recipes/weg").mock(side_effect=httpx.ConnectError("x"))
    antwort = client.get("/api/rezepte/weg")
    assert antwort.status_code == 502 and "nicht erreichbar" in antwort.json()["detail"]


def test_rezeptliste(app_client):
    client, mock = app_client
    mock.get(f"{BASIS}/api/recipes").mock(
        return_value=httpx.Response(200, json={"page": 1, "total": 1, "total_pages": 1, "items": [{"id": "i", "slug": "s", "name": "N", "image": "x"}]})
    )
    daten = client.get("/api/rezepte?suche=n").json()
    assert daten["gesamt"] == 1 and daten["rezepte"][0] == {"id": "i", "slug": "s", "name": "N", "hat_bild": True}


def test_bild_nur_erlaubte_dateien(app_client):
    client, mock = app_client
    rid = "11111111-1111-1111-1111-111111111111"
    mock.get(f"{BASIS}/api/media/recipes/{rid}/images/min-original.webp").mock(
        return_value=httpx.Response(200, content=b"RIFF", headers={"content-type": "image/webp"})
    )
    assert client.get(f"/api/bild/{rid}").content == b"RIFF"
    assert client.get(f"/api/bild/{rid}?datei=../../etc/passwd").status_code == 400
    assert client.get("/api/bild/nicht-gueltig").status_code == 422


def test_oberflaeche_wird_nie_veraltet_ausgeliefert(app_client):
    client, _ = app_client
    for pfad in ("/", "/app.js", "/style.css", "/sw.js", "/manifest.webmanifest"):
        antwort = client.get(pfad)
        assert antwort.status_code == 200, pfad
        assert antwort.headers["cache-control"] == "no-cache", pfad


def test_wach_videos_werden_ausgeliefert(app_client):
    """Ersatz fürs Wachhalten ohne HTTPS: beide Videodateien müssen mit Videotyp erreichbar sein."""
    client, _ = app_client
    for datei, typ in (("wach.mp4", "video/mp4"), ("wach.webm", "video/webm")):
        r = client.get(f"/{datei}")
        assert r.status_code == 200
        assert r.headers["content-type"].startswith(typ)
        assert len(r.content) > 100

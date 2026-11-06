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


# --- Foto-/Text-Import per KI -------------------------------------------------
JPEG = b"\xff\xd8\xff\xe0" + b"0" * 64
PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 64


def test_ki_import_reicht_fotos_und_text_an_mealie(app_client):
    client, mock = app_client
    route = mock.post(f"{BASIS}/api/recipes/create/ai").mock(return_value=httpx.Response(201, json="mein-rezept"))
    antwort = client.post(
        "/api/import-ki",
        files=[("bilder", ("a.jpg", JPEG, "image/jpeg")), ("bilder", ("b.png", PNG, "image/png"))],
        data={"text": "  Notiz: Salz weglassen  "},
    )
    assert antwort.status_code == 201 and antwort.json() == {"slug": "mein-rezept"}
    gesendet = route.calls.last.request
    assert gesendet.headers["authorization"] == "Bearer tok"
    assert gesendet.content.count(b'name="images"') == 2
    assert b"Notiz: Salz weglassen" in gesendet.content


def test_ki_import_nur_text(app_client):
    client, mock = app_client
    mock.post(f"{BASIS}/api/recipes/create/ai").mock(return_value=httpx.Response(201, json="text-rezept"))
    assert client.post("/api/import-ki", data={"text": "200 g Mehl\nVerrühren"}).json() == {"slug": "text-rezept"}


def test_ki_import_zeigt_mealie_fehlertext(app_client):
    client, mock = app_client
    mock.post(f"{BASIS}/api/recipes/create/ai").mock(
        return_value=httpx.Response(400, json={"detail": {"message": "AI is not enabled"}})
    )
    antwort = client.post("/api/import-ki", data={"text": "etwas"})
    assert antwort.status_code == 502 and "AI is not enabled" in antwort.json()["detail"]


def test_ki_import_ohne_eingabe(app_client):
    client, _ = app_client
    assert client.post("/api/import-ki").status_code == 422


def test_ki_import_falsches_format(app_client):
    client, _ = app_client
    antwort = client.post("/api/import-ki", files=[("bilder", ("x.jpg", b"<html>kein bild</html>", "image/jpeg"))])
    assert antwort.status_code == 422 and "Format" in antwort.json()["detail"]


def test_ki_import_zu_viele_fotos(app_client):
    client, _ = app_client
    antwort = client.post("/api/import-ki", files=[("bilder", (f"{i}.jpg", JPEG, "image/jpeg")) for i in range(7)])
    assert antwort.status_code == 422 and "höchstens 6" in antwort.json()["detail"]


def test_ki_import_zu_gross(app_client):
    client, _ = app_client
    gross = b"\xff\xd8\xff" + b"0" * (10 * 1024 * 1024 + 1)
    antwort = client.post("/api/import-ki", files=[("bilder", ("gross.jpg", gross, "image/jpeg"))])
    assert antwort.status_code == 413


@pytest.mark.parametrize("pfad,daten", [("/api/import", None), ("/api/import-ki", {"url": "x"})])
def test_cookidoo_link_wird_abgelehnt(app_client, pfad, daten):
    client, mock = app_client
    ziel = "https://cookidoo.de/recipes/recipe/de-DE/r123"
    if pfad == "/api/import":
        antwort = client.post(pfad, json={"url": ziel})
    else:
        antwort = client.post(pfad, data={"url": ziel})
    assert antwort.status_code == 422
    assert "Cookidoo" in str(antwort.json()) and not mock.calls.call_count


def test_foto_import_markiert_rezept_als_ki_gelesen(app_client):
    client, mock = app_client
    mock.post(f"{BASIS}/api/recipes/create/ai").mock(return_value=httpx.Response(201, json="testsuppe"))
    assert client.get("/api/rezepte/testsuppe").json()["ki_gelesen"] is False
    client.post("/api/import-ki", files=[("bilder", ("a.jpg", JPEG, "image/jpeg"))])
    r = client.get("/api/rezepte/testsuppe").json()
    assert r["ki_gelesen"] is True and r["offen"] > 1
    # nach "Passt so" ist die Einstellung bestätigt
    url = "/api/rezepte/testsuppe/schritte/s1/einstellungen/0"
    antwort = client.put(url, json={"werte": {"dauer_s": 6, "stufe": 5, "art": "stufe"}})
    assert antwort.status_code == 200
    e = client.get("/api/rezepte/testsuppe").json()["schritte"][0]["einstellungen"][0]
    assert e["status"] == "bestaetigt" and e["dauer_s"] == 6


def test_nur_text_import_wird_nicht_markiert(app_client):
    client, mock = app_client
    mock.post(f"{BASIS}/api/recipes/create/ai").mock(return_value=httpx.Response(201, json="testsuppe"))
    client.post("/api/import-ki", data={"text": "200 g Mehl verrühren"})
    assert client.get("/api/rezepte/testsuppe").json()["ki_gelesen"] is False

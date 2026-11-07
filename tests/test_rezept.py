"""Tests für die Aufbereitung eines Mealie-Rezepts und die Speicherung der Bestätigungen."""

from app.rezept import aufbereiten
from app.speicher import Speicher

# Nachgestellt nach dem Mealie-Schema v3.30.0 (camelCase), Inhalte selbst erfunden.
MEALIE_REZEPT = {
    "id": "11111111-1111-1111-1111-111111111111",
    "slug": "testsuppe",
    "name": "Testsuppe",
    "description": "Eine einfache Suppe zum Testen.",
    "image": "abcd",
    "recipeServings": 4,
    "recipeYieldQuantity": 0,
    "recipeIngredient": [
        {
            "referenceId": "z1",
            "quantity": 500,
            "unit": {"name": "Gramm", "abbreviation": "g", "useAbbreviation": True},
            "food": {"name": "Kartoffeln"},
            "note": "mehligkochend",
            "display": "500 g Kartoffeln mehligkochend",
            "title": None,
        },
        {"referenceId": "z2", "quantity": 0, "unit": None, "food": None, "display": "", "originalText": "Salz nach Geschmack"},
    ],
    "recipeInstructions": [
        {
            "id": "s1",
            "title": "Vorbereiten",
            "text": "Zwiebel in den Mixtopf geben und 5 Sek./Stufe 5 zerkleinern.",
            "ingredientReferences": [{"referenceId": "z1"}],
        },
        {"id": "s2", "title": "", "text": "Kartoffeln zugeben, 15 Min./100 °C/Stufe 1 garen. 10 Min. ruhen lassen."},
        {"id": "s3", "title": "", "text": "Jetzt 5 Min./100 °C kochen."},
        {"id": "s4", "title": "", "text": "Mit Salz abschmecken."},
    ],
}


def test_grundaufbau():
    r = aufbereiten(MEALIE_REZEPT)
    assert (r["slug"], r["name"], r["portionen"], r["hat_bild"]) == ("testsuppe", "Testsuppe", 4, True)
    assert len(r["schritte"]) == 4 and len(r["zutaten"]) == 2


def test_zutaten():
    z1, z2 = aufbereiten(MEALIE_REZEPT)["zutaten"]
    assert (z1["menge"], z1["einheit"], z1["name"], z1["notiz"]) == (500, "g", "Kartoffeln", "mehligkochend")
    assert z2["menge"] is None and z2["anzeige"] == "Salz nach Geschmack"  # Freitext bleibt erhalten


def test_schritte_mit_einstellungen_und_zeiten():
    s = aufbereiten(MEALIE_REZEPT)["schritte"]
    assert s[0]["titel"] == "Vorbereiten" and s[0]["zutaten"] == ["z1"]
    e = s[0]["einstellungen"][0]
    assert (e["dauer_s"], e["stufe"], e["status"]) == (5, 5, "ok")
    assert s[1]["einstellungen"][0]["temperatur_c"] == 100
    assert [z["dauer_s"] for z in s[1]["zeiten"]] == [600]
    assert s[3]["einstellungen"] == []


def test_unsicheres_wird_markiert_und_gezaehlt():
    r = aufbereiten(MEALIE_REZEPT)
    e = r["schritte"][2]["einstellungen"][0]
    assert e["status"] == "pruefen" and [h["code"] for h in e["hinweise"]] == ["STUFE_FEHLT"]
    assert r["offen"] == 1


def test_bestaetigung_gilt_nur_bei_gleichem_text():
    quelle = "5 Min./100 °C"
    werte = {"dauer_s": 300, "temperatur_c": 100, "stufe": 1, "art": "stufe", "varoma": False, "linkslauf": False}
    r = aufbereiten(MEALIE_REZEPT, {("s3", 0): {"quelle": quelle, "werte": werte}})
    e = r["schritte"][2]["einstellungen"][0]
    assert e["status"] == "bestaetigt" and e["stufe"] == 1 and r["offen"] == 0
    # Rezepttext wurde in Mealie geändert -> Bestätigung verfällt
    r2 = aufbereiten(MEALIE_REZEPT, {("s3", 0): {"quelle": "7 Min./100 °C", "werte": werte}})
    assert r2["schritte"][2]["einstellungen"][0]["status"] == "pruefen"


def test_ohne_schrittid_wird_der_index_genutzt():
    r = aufbereiten({"slug": "x", "recipeInstructions": [{"text": "10 Sek./Stufe 5"}]})
    assert r["schritte"][0]["id"] == "0"


def test_leeres_rezept():
    r = aufbereiten({})
    assert r["schritte"] == [] and r["zutaten"] == [] and r["portionen"] is None


def test_speicher_roundtrip(tmp_path):
    sp = Speicher(tmp_path / "daten")
    assert sp.laden("a") == {}
    sp.bestaetigen("a", "s1", 0, "5 Min./100 °C", {"stufe": 2})
    sp.bestaetigen("a", "s1", 0, "5 Min./100 °C", {"stufe": 3})  # überschreibt
    assert sp.laden("a") == {("s1", 0): {"quelle": "5 Min./100 °C", "werte": {"stufe": 3}}}
    assert sp.laden("b") == {}
    sp.zuruecknehmen("a", "s1", 0)
    assert sp.laden("a") == {}


# --- Rezepte, die per KI aus einem Foto gelesen wurden ---
def test_ki_rezept_markiert_auch_plausible_werte():
    normal = aufbereiten(MEALIE_REZEPT)
    ki = aufbereiten(MEALIE_REZEPT, ki_gelesen=True)
    assert normal["ki_gelesen"] is False and ki["ki_gelesen"] is True
    e = ki["schritte"][0]["einstellungen"][0]
    assert e["status"] == "pruefen" and any(h["code"] == "KI_GELESEN" for h in e["hinweise"])
    gesamt = sum(len(s["einstellungen"]) for s in ki["schritte"])
    assert ki["offen"] == gesamt  # jede Einstellung braucht einmal "Passt so"


def test_ki_rezept_bestaetigung_gilt():
    ki = aufbereiten(
        MEALIE_REZEPT,
        {("s1", 0): {"quelle": "5 Sek./Stufe 5", "werte": {"dauer_s": 6}}},
        ki_gelesen=True,
    )
    e = ki["schritte"][0]["einstellungen"][0]
    assert e["status"] == "bestaetigt" and e["dauer_s"] == 6


# --- Platzhalter von Quellen, die Schritte nur Mitgliedern zeigen ---
def test_platzhalter_schritt_wird_zum_hinweis():
    r = aufbereiten({"slug": "x", "recipeInstructions": [{"text": "Recipe steps as well as other fields are only available for members."}]})
    assert r["schritte"] == [] and r["schritte_gesperrt"] is True


def test_normales_rezept_ist_nicht_gesperrt():
    assert aufbereiten(MEALIE_REZEPT)["schritte_gesperrt"] is False
    assert aufbereiten({})["schritte_gesperrt"] is False


def test_echte_schritte_bleiben_neben_platzhalter():
    r = aufbereiten({"recipeInstructions": [{"text": "Recipe steps as well as other fields …"}, {"text": "10 Sek./Stufe 5"}]})
    assert len(r["schritte"]) == 1 and r["schritte_gesperrt"] is False

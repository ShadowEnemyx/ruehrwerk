"""Tests für den Parser: erkennt Zeit, Temperatur, Stufe und Sonderangaben in deutschen Rezepttexten.

Alle Beispielsätze sind selbst formuliert (keine Rezepte aus fremden Quellen kopiert).
"""

import pytest

from app.parser.thermomix import parse_schritt


def E(d=None, t=None, s=None, art=None, v=False, l=False, w=1):
    """Kurzschreibweise für das erwartete Ergebnis einer Einstellung."""
    if art is None:
        art = "stufe" if s is not None else "keine"
    return {"dauer_s": d, "temperatur_c": t, "varoma": v, "stufe": s, "art": art, "linkslauf": l, "wiederholungen": w}


def kurz(einstellung):
    return {
        "dauer_s": einstellung.dauer_s,
        "temperatur_c": einstellung.temperatur_c,
        "varoma": einstellung.varoma,
        "stufe": einstellung.stufe,
        "art": einstellung.art,
        "linkslauf": einstellung.linkslauf,
        "wiederholungen": einstellung.wiederholungen,
    }


# (Satz, erwartete Einstellungen)
FAELLE = [
    # --- Grundformen ---
    ("Zwiebeln in den Mixtopf geben und 10 Sek./Stufe 5 zerkleinern.", [E(d=10, s=5)]),
    ("3 Min./100°C/Stufe 1", [E(d=180, t=100, s=1)]),
    ("3 Min./100 °C/Stufe 1", [E(d=180, t=100, s=1)]),
    ("3 Min. / 100 °C / Stufe 1", [E(d=180, t=100, s=1)]),
    ("3 Min., 100 °C, Stufe 1", [E(d=180, t=100, s=1)]),
    ("Alles 3 Min. bei 100 °C auf Stufe 1 garen.", [E(d=180, t=100, s=1)]),
    ("3 Min. 100 Grad Stufe 1", [E(d=180, t=100, s=1)]),
    ("3 Min./100 Grad C/Stufe 1", [E(d=180, t=100, s=1)]),
    ("3 Min./100° C/Stufe 1", [E(d=180, t=100, s=1)]),
    ("3 Min./100ºC/Stufe 1", [E(d=180, t=100, s=1)]),
    # --- Schreibvarianten der Zeit ---
    ("10 Sek/Stufe 5", [E(d=10, s=5)]),
    ("10 Sekunden/Stufe 5", [E(d=10, s=5)]),
    ("2 Minuten/Stufe 4", [E(d=120, s=4)]),
    ("1 Minute/Stufe 4", [E(d=60, s=4)]),
    ("5 Min/Stufe 2", [E(d=300, s=2)]),
    ("1 Min. 30 Sek./Stufe 2", [E(d=90, s=2)]),
    ("1 Min. und 30 Sek./Stufe 2", [E(d=90, s=2)]),
    ("1:30 Min./Stufe 2", [E(d=90, s=2)]),
    ("1,5 Min./Stufe 2", [E(d=90, s=2)]),
    ("0,5 Sek./Turbo", [E(d=0.5, art="turbo")]),
    ("10 SEK./STUFE 5", [E(d=10, s=5)]),
    ("10 Sek./Stufe 5", [E(d=10, s=5)]),
    # --- Stufen ---
    ("30 Sek./Stufe 0,5", [E(d=30, s=0.5)]),
    ("5 Sek./Stufe 0.5", [E(d=5, s=0.5)]),
    ("5 Sek./Stufe 10", [E(d=5, s=10)]),
    ("20 Sek./Stufe 8 pürieren", [E(d=20, s=8)]),
    ("Alles 4 Sek./Stufe 4 vermischen.", [E(d=4, s=4)]),
    # --- Turbo ---
    ("1 Sek./Turbo", [E(d=1, art="turbo")]),
    ("1 Sek. Turbo", [E(d=1, art="turbo")]),
    ("3 x 1 Sek./Turbo", [E(d=1, art="turbo", w=3)]),
    ("2x 1 Sek./Turbo zerkleinern", [E(d=1, art="turbo", w=2)]),
    # --- Linkslauf, Sanftrühr-, Teigknetstufe ---
    ("20 Min./90 °C/Linkslauf/Stufe 1", [E(d=1200, t=90, s=1, l=True)]),
    ("20 Min./90 °C/Stufe 1/Linkslauf", [E(d=1200, t=90, s=1, l=True)]),
    ("6 Min./80 °C/Linkslauf/Stufe 1 rühren", [E(d=360, t=80, s=1, l=True)]),
    ("20 Min./90 °C/Sanftrührstufe", [E(d=1200, t=90, art="sanftruehr")]),
    ("5 Min./Sanftrührstufe", [E(d=300, art="sanftruehr")]),
    ("2 Min./Teigknetstufe", [E(d=120, art="teigknet")]),
    ("Zu einem Teig verkneten: 3 Min./Teigknetstufe.", [E(d=180, art="teigknet")]),
    ("5 Min./Linkslauf", [E(d=300, l=True)]),
    # --- Varoma ---
    ("5 Min./Varoma/Stufe 1", [E(d=300, v=True, s=1)]),
    ("20 Min./Varoma/Stufe 1 garen", [E(d=1200, v=True, s=1)]),
    ("20 Min./Varoma-Temperatur/Stufe 1", [E(d=1200, v=True, s=1)]),
    ("Varoma-Aufsatz aufsetzen und 20 Min./Varoma/Stufe 1 garen.", [E(d=1200, v=True, s=1)]),
    ("Varoma-Behälter einsetzen.", []),
    ("Den Varoma auf den Mixtopf setzen.", []),
    ("Varoma-Einlegeboden einlegen und das Gemüse darauflegen.", []),
    # --- Temperaturen ---
    ("2 Min./37 °C/Stufe 2", [E(d=120, t=37, s=2)]),
    ("4 Min./120 °C/Stufe 1", [E(d=240, t=120, s=1)]),
    ("5 Min./50 °C/Stufe 3", [E(d=300, t=50, s=3)]),
    # --- Mehrere Einstellungen in einem Schritt ---
    (
        "10 Sek./Stufe 5 zerkleinern, dann 3 Min./100 °C/Stufe 1 andünsten.",
        [E(d=10, s=5), E(d=180, t=100, s=1)],
    ),
    ("5 Sek./Stufe 5 zerkleinern. 10 Min./100°C/Stufe 1", [E(d=5, s=5), E(d=600, t=100, s=1)]),
    ("2 Min. / Stufe 3, 5 Min. / 100 °C / Stufe 2", [E(d=120, s=3), E(d=300, t=100, s=2)]),
    ("10 Sek./Stufe 5/5 Sek./Stufe 8", [E(d=10, s=5), E(d=5, s=8)]),
    # --- Nur Teilangaben (werden erkannt, später von der Plausibilitätsprüfung markiert) ---
    ("Auf Stufe 5 hochfahren.", [E(s=5)]),
    ("5 Min./100 °C", [E(d=300, t=100)]),
    # --- Bereiche: der untere Wert ist der Vorschlag, der Bereich wird gemerkt ---
    ("2-3 Min./100 °C/Stufe 1", [E(d=120, t=100, s=1)]),
    ("2–3 Min./Stufe 3", [E(d=120, s=3)]),
    ("3 Min./Stufe 4-5", [E(d=180, s=4)]),
    ("10 Min./90-100 °C/Stufe 1", [E(d=600, t=90, s=1)]),
    # --- Backofen und Ähnliches ist KEINE Thermomix-Einstellung ---
    ("Backofen auf 180 °C Ober-/Unterhitze vorheizen.", []),
    ("Im vorgeheizten Backofen bei 180 °C 25 Min. backen.", []),
    ("Bei 200 °C Umluft 12 Min. backen.", []),
    ("Die Pfanne auf 180 Grad erhitzen.", []),
    ("Den Ofen auf 220 °C vorheizen und das Blech einschieben.", []),
    # --- Schreibweisen aus echten Rezepten: "St." für Stufe, "100 C" ohne Gradzeichen ---
    ("Zwiebel und Knoblauch hacken: 5 Sek/St. 5 hacken.", [E(d=5, s=5)]),
    ("Öl zugeben und 2min/100 C/St. 1 dünsten", [E(d=120, t=100, s=1)]),
    ("5min/100 C/ St. 2,5 kochen.", [E(d=300, t=100, s=2.5)]),
    ("3 Min./100 C/St 1", [E(d=180, t=100, s=1)]),
    ("10 Sek./St.5", [E(d=10, s=5)]),
    ("Bei 180 C für 25 min im vorgeheizten Backofen überbacken", []),
    ("Mit 2 Stück 5 Min. ruhen lassen.", []),
    # --- Texte ohne Einstellung ---
    ("30 Min. im Kühlschrank ruhen lassen.", []),
    ("Teig 1 Std. gehen lassen.", []),
    ("2 Std. 30 Min. ziehen lassen.", []),
    ("100 g Mehl, 2 EL Öl und 50 ml Wasser in den Mixtopf geben.", []),
    ("Mit dem Spatel nach unten schieben.", []),
    ("Auf kleiner Stufe köcheln lassen.", []),
    ("Den Herd auf Herdstufe 3 stellen.", []),
    ("Temperatur 120 °C", []),
    ("100 °C", []),
    ("Linkslauf", []),
    ("", []),
]


@pytest.mark.parametrize("satz,erwartet", FAELLE)
def test_einstellungen(satz, erwartet):
    ergebnis = parse_schritt(satz)
    assert [kurz(e) for e in ergebnis.einstellungen] == erwartet


def test_originaltext_der_einstellung():
    satz = "Zwiebeln in den Mixtopf geben und 10 Sek./Stufe 5 zerkleinern."
    e = parse_schritt(satz).einstellungen[0]
    assert e.text == "10 Sek./Stufe 5"
    assert satz[e.start : e.ende] == e.text


def test_originaltext_mehrere():
    ergebnis = parse_schritt("10 Sek./Stufe 5 zerkleinern, dann 3 Min./100 °C/Stufe 1 andünsten.")
    assert [e.text for e in ergebnis.einstellungen] == ["10 Sek./Stufe 5", "3 Min./100 °C/Stufe 1"]


def test_bereiche_werden_gemerkt():
    e = parse_schritt("2-3 Min./90-100 °C/Stufe 4-5").einstellungen[0]
    assert (e.dauer_s, e.dauer_max_s) == (120, 180)
    assert (e.temperatur_c, e.temperatur_max_c) == (90, 100)
    assert (e.stufe, e.stufe_max) == (4, 5)


def test_kein_bereich_bei_einzelwerten():
    e = parse_schritt("3 Min./100 °C/Stufe 1").einstellungen[0]
    assert e.dauer_max_s is None and e.temperatur_max_c is None and e.stufe_max is None


# --- einfache Zeiten außerhalb von Einstellungen (für Timer im Kochmodus) ---
@pytest.mark.parametrize(
    "satz,erwartet",
    [
        ("30 Min. im Kühlschrank ruhen lassen.", [1800]),
        ("Teig 1 Std. gehen lassen.", [3600]),
        ("2 Std. 30 Min. ziehen lassen.", [9000]),
        ("Im vorgeheizten Backofen bei 180 °C 25 Min. backen.", [1500]),
        ("10 Sek./Stufe 5 zerkleinern.", []),
        ("Alles vermischen.", []),
    ],
)
def test_zeiten_ausserhalb(satz, erwartet):
    assert [z.dauer_s for z in parse_schritt(satz).zeiten] == erwartet


# --- knifflige Fälle ---
KNIFFLIG = [
    ("Fisch in den Varoma legen, Varoma auf den Mixtopf setzen und 20 Min./Varoma/Stufe 1 garen.", [E(d=1200, v=True, s=1)]),
    ("Mixtopf verschließen, 5 Sek./Stufe 7 zerkleinern und mit dem Spatel nach unten schieben. 3 Min./100 °C/Stufe 1 dünsten.", [E(d=5, s=7), E(d=180, t=100, s=1)]),
    ("Aus der Masse Minifrikadellen formen.", []),
    ("Mindestens 2 Stunden durchziehen lassen.", []),
    ("12 Min./100 °C/Stufe 2 kochen, dabei den Messbecher aufsetzen.", [E(d=720, t=100, s=2)]),
    ("2 bis 3 Min./Stufe 4", [E(d=120, s=4)]),
    ("5 Min./Stufe 1 bis 2", [E(d=300, s=1)]),
    ("Ca. 10 Sek./Stufe 6 pürieren.", [E(d=10, s=6)]),
    ("1 Std. 10 Min./100 °C/Stufe 1", [E(d=4200, t=100, s=1)]),
    ("Das Ei 6 Min. kochen, dann abschrecken.", []),
]


@pytest.mark.parametrize("satz,erwartet", KNIFFLIG)
def test_knifflig(satz, erwartet):
    assert [kurz(e) for e in parse_schritt(satz).einstellungen] == erwartet

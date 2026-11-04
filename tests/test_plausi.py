"""Tests für die Plausibilitätsprüfung: unsichere Werte werden markiert, nie still übernommen."""

import pytest

from app.parser.plausi import GRENZEN, pruefe
from app.parser.thermomix import parse_schritt


def codes(satz):
    e = parse_schritt(satz).einstellungen[0]
    return sorted(h.code for h in pruefe(e))


@pytest.mark.parametrize(
    "satz",
    [
        "3 Min./100 °C/Stufe 1",
        "10 Sek./Stufe 5",
        "2 Min./37 °C/Stufe 2",
        "5 Min./40 °C/Stufe 1",
        "4 Min./120 °C/Stufe 1",
        "20 Min./Varoma/Stufe 1",
        "20 Min./90 °C/Linkslauf/Stufe 1",
        "20 Min./90 °C/Sanftrührstufe",
        "3 Min./Teigknetstufe",
        "1 Sek./Turbo",
        "3 x 1 Sek./Turbo",
        "30 Sek./Stufe 0,5",
        "5 Sek./Stufe 10",
        "3 Min./60 °C/Stufe 6",
    ],
)
def test_unauffaellig(satz):
    assert codes(satz) == []


@pytest.mark.parametrize(
    "satz,erwartet",
    [
        ("Auf Stufe 5 hochfahren.", ["ZEIT_FEHLT"]),
        ("5 Min./100 °C/Stufe 2 kochen", []),
        ("5 Min./100 °C", ["STUFE_FEHLT"]),
        ("5 Min./Linkslauf", ["STUFE_FEHLT"]),
        ("2-3 Min./Stufe 3", ["BEREICH_ZEIT"]),
        ("3 Min./Stufe 4-5", ["BEREICH_STUFE"]),
        ("10 Min./90-100 °C/Stufe 1", ["BEREICH_TEMP"]),
        ("2-3 Min./90-100 °C/Stufe 4-5", ["BEREICH_STUFE", "BEREICH_TEMP", "BEREICH_ZEIT"]),
        ("3 Min./101 °C/Stufe 1", ["TEMP_UNGUELTIG"]),
        ("3 Min./130 °C/Stufe 1", ["TEMP_UNGUELTIG"]),
        ("3 Min./20 °C/Stufe 1", ["TEMP_UNGUELTIG"]),
        ("3 Min./Stufe 11", ["STUFE_UNGUELTIG"]),
        ("3 Min./Stufe 0,3", ["STUFE_UNGUELTIG"]),
        ("3 Min./Stufe 2,5", ["STUFE_UNGUELTIG"]),
        ("3 Min./100 °C/Stufe 8", ["HEISS_SCHNELL"]),
        ("3 Min./61 °C/Stufe 7", ["TEMP_UNGUELTIG", "HEISS_SCHNELL"]),
        ("3 Min./Varoma/Stufe 8", ["HEISS_SCHNELL"]),
        ("3 Min./Linkslauf/Stufe 5", ["LINKSLAUF_SCHNELL"]),
        ("3 Min./50 °C/Linkslauf/Stufe 9", ["LINKSLAUF_SCHNELL"]),
        ("1 Sek./50 °C/Turbo", ["TURBO_MIT_TEMP"]),
        ("3 Min./100 °C/Teigknetstufe", ["TEIG_MIT_TEMP"]),
        ("2 Std./90 °C/Stufe 1", ["ZEIT_LANG"]),
        ("0 Sek./Stufe 3", ["ZEIT_UNGUELTIG"]),
    ],
)
def test_auffaellig(satz, erwartet):
    assert codes(satz) == sorted(erwartet)


def test_hinweis_hat_klartext():
    e = parse_schritt("5 Min./100 °C").einstellungen[0]
    h = pruefe(e)[0]
    assert h.code == "STUFE_FEHLT"
    assert "Stufe" in h.text  # verständlicher deutscher Text für die Oberfläche


def test_grenzen_stehen_an_einer_stelle():
    """Alle Schwellwerte liegen in GRENZEN, damit man sie leicht anpassen kann."""
    assert GRENZEN.heiss_ab_c == 60
    assert GRENZEN.hohe_stufe_ab == 7
    assert GRENZEN.linkslauf_max_stufe == 4
    assert GRENZEN.lange_zeit_ab_s == 3600
    assert 37 in GRENZEN.temperaturen and 120 in GRENZEN.temperaturen and 100 in GRENZEN.temperaturen
    assert 101 not in GRENZEN.temperaturen
    assert 0.5 in GRENZEN.stufen and 10 in GRENZEN.stufen and 2.5 not in GRENZEN.stufen

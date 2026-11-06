"""Erkennt Thermomix®-Angaben (Zeit, Temperatur, Stufe, Sonderangaben) in deutschen Rezepttexten.

Arbeitsweise in drei Schritten:
1. Ein großer regulärer Ausdruck findet einzelne "Bausteine" (Zeit, Temperatur, Stufe, ...).
2. Bausteine, die nur durch Trennzeichen wie "/" oder "," getrennt sind, werden zu einer Einstellung
   zusammengefasst ("3 Min./100°C/Stufe 1"). Taucht ein Bausteintyp ein zweites Mal auf, beginnt eine neue.
3. Gruppen werden verworfen, die keine Geräteeinstellung sind (z. B. Backofen-Temperaturen).

Der Parser entscheidet nur, WAS im Text steht. Ob die Werte sinnvoll sind, prüft app/parser/plausi.py.
"""

import re

from .modell import Einstellung, SchrittErgebnis, Zeit

BUCH = "A-Za-zÄÖÜäöüß"
ZAHL = r"\d+(?:[.,]\d+)?"
ENDE = rf"(?![{BUCH}])"  # danach darf kein Buchstabe folgen ("Min" ja, "Mindestens" nein)
KEINE_ZAHL_DAVOR = r"(?<![\d,.:])"
BEREICH = r"(?:\s*[-–]\s*|\s+bis\s+)"  # "2-3" oder "2 bis 3"
BEREICH_STUFE = r"(?:[-–]|\s+bis\s+)"  # bei Stufen enger, sonst wird "Stufe 1 - 5 Min." falsch gelesen

STD = rf"(?:Stunden|Stunde|Std\.?){ENDE}"
MIN = rf"(?:Minuten|Minute|Min\.?){ENDE}"
SEK = rf"(?:Sekunden|Sekunde|Sek\.?|Sec\.?){ENDE}"  # "sec" schreiben KI-Texte aus Fotos manchmal
ZEITTEIL = rf"{ZAHL}(?:{BEREICH}{ZAHL})?\s*(?:{STD}|{MIN}|{SEK})"
ZEIT = (
    rf"{KEINE_ZAHL_DAVOR}(?:(?P<wdh>\d+)\s*[x×]\s*)?"
    rf"(?:(?P<mmss>\d{{1,2}}:\d{{2}})\s*{MIN}|{ZEITTEIL}(?:\s*(?:und\s+)?{ZEITTEIL})*)"
)
TEMP = (
    rf"{KEINE_ZAHL_DAVOR}{ZAHL}(?:{BEREICH}{ZAHL})?\s*"
    rf"(?:°\s*(?:C(?:elsius)?{ENDE})?|Grad(?:\s*C(?:elsius)?)?{ENDE}|C{ENDE})"
)
# "Varoma" als Temperaturangabe, aber nicht der Aufsatz ("Varoma-Aufsatz", "Varoma-Behälter" ...)
VAROMA = (
    rf"(?<![{BUCH}])Varoma(?:-?\s*Temperatur)?(?![{BUCH}])"
    rf"(?!-\s*(?:Aufsatz|Behälter|Einlegeboden|Deckel|Schale|Gericht|Gar|Schüssel))"
)
SANFT = rf"(?<![{BUCH}])Sanftr(?:ü|ue)hr-?stufe{ENDE}"
TEIG = rf"(?<![{BUCH}])Teigknet-?stufe{ENDE}"
STUFE = rf"(?<![{BUCH}])(?:Stufe|St\.?{ENDE})\s*(?P<s1>{ZAHL})(?:{BEREICH_STUFE}(?P<s2>{ZAHL}))?"
TURBO = rf"(?<![{BUCH}])Turbo(?:-?\s*(?:Stufe|Taste))?{ENDE}"
LINKS = rf"(?<![{BUCH}])Linkslauf{ENDE}"

BAUSTEINE = re.compile(
    rf"(?P<zeit>{ZEIT})|(?P<temp>{TEMP})|(?P<varoma>{VAROMA})|(?P<sanft>{SANFT})|(?P<teig>{TEIG})"
    rf"|(?P<stufe>{STUFE})|(?P<turbo>{TURBO})|(?P<links>{LINKS})",
    re.IGNORECASE,
)
ZEITTEIL_RE = re.compile(
    rf"(?P<a>{ZAHL})(?:{BEREICH}(?P<b>{ZAHL}))?\s*(?:(?P<std>{STD})|(?P<min>{MIN})|(?P<sek>{SEK}))", re.IGNORECASE
)
TEMP_RE = re.compile(rf"(?P<a>{ZAHL})(?:{BEREICH}(?P<b>{ZAHL}))?", re.IGNORECASE)

# Trennstücke, die zwei Bausteine zu einer Einstellung verbinden: "/", ",", "auf", "bei" ...
VERBINDER = re.compile(r"\s*(?:[/|,;·•]\s*)?(?:(?:und|auf|bei|mit|im|in|sowie)\s+)?", re.IGNORECASE)

# Wörter, die zeigen: "180 °C" ist eine Backofen-/Pfannen-Angabe und keine Mixtopf-Einstellung
OFEN_WORTE = re.compile(
    r"backofen|ofen|umluft|ober-|unterhitze|oberhitze|heißluft|heissluft|grill|backblech|backen|pfanne",
    re.IGNORECASE,
)
OFEN_FENSTER = 80  # so viele Zeichen vor und nach der Gruppe werden auf Backofen-Wörter geprüft

# Zeichen, die gleich aussehen, aber anders kodiert sind – gleiche Länge, damit Positionen stimmen
NORMALISIEREN = str.maketrans(
    {"º": "°", "˚": "°", " ": " ", " ": " ", " ": " ", "−": "-", "‑": "-"}
)

SPEED_TYPEN = {"stufe", "sanft", "teig", "turbo"}


def _zahl(text: str) -> float:
    """Wandelt "0,5" in 0.5 um; ganze Zahlen bleiben ganze Zahlen."""
    wert = float(text.replace(",", "."))
    return int(wert) if wert.is_integer() else wert


def _gruppe_typ(art: str) -> str:
    """Gruppiert die Bausteintypen: Zwei Bausteine derselben Gruppe gehören nie zur selben Einstellung."""
    if art in SPEED_TYPEN:
        return "speed"
    if art in ("temp", "varoma"):
        return "temp"
    return art  # "zeit" oder "links"


def _dauer(match: re.Match) -> tuple[float, float | None]:
    """Berechnet (Dauer, Obergrenze) in Sekunden aus einem Zeit-Baustein."""
    if match.group("mmss"):
        minuten, sekunden = match.group("mmss").split(":")
        wert = int(minuten) * 60 + int(sekunden)
        return wert, None
    unten = oben = 0.0
    ist_bereich = False
    for teil in ZEITTEIL_RE.finditer(match.group("zeit")):
        faktor = 3600 if teil.group("std") else 60 if teil.group("min") else 1
        a = _zahl(teil.group("a"))
        b = _zahl(teil.group("b")) if teil.group("b") else a
        ist_bereich = ist_bereich or teil.group("b") is not None
        unten += a * faktor
        oben += b * faktor
    return _zahl(str(unten)), (_zahl(str(oben)) if ist_bereich and oben != unten else None)


def _bausteine(text: str) -> list[tuple[str, re.Match]]:
    gefunden = []
    for m in BAUSTEINE.finditer(text):
        art = m.lastgroup
        # lastgroup ist bei verschachtelten Gruppen nicht immer der Haupttyp -> gezielt suchen
        for kandidat in ("zeit", "temp", "varoma", "sanft", "teig", "stufe", "turbo", "links"):
            if m.group(kandidat) is not None:
                art = kandidat
                break
        gefunden.append((art, m))
    return gefunden


def _gruppieren(text: str, bausteine: list[tuple[str, re.Match]]) -> list[list[tuple[str, re.Match]]]:
    gruppen: list[list[tuple[str, re.Match]]] = []
    for art, m in bausteine:
        if gruppen:
            letzte = gruppen[-1]
            zwischen = text[letzte[-1][1].end() : m.start()]
            belegt = {_gruppe_typ(a) for a, _ in letzte}
            if VERBINDER.fullmatch(zwischen) and _gruppe_typ(art) not in belegt:
                letzte.append((art, m))
                continue
        gruppen.append([(art, m)])
    return gruppen


def _zeit_aus(text: str, art_m: tuple[str, re.Match]) -> Zeit:
    _, m = art_m
    dauer, maximum = _dauer(m)
    roh = m.group("zeit")
    ende = m.start() + len(roh.rstrip())
    return Zeit(text=text[m.start() : ende], start=m.start(), ende=ende, dauer_s=dauer, dauer_max_s=maximum)


def parse_schritt(text: str) -> SchrittErgebnis:
    """Liest einen Rezeptschritt und liefert alle erkannten Einstellungen und einfachen Zeiten."""
    norm = text.translate(NORMALISIEREN)
    einstellungen: list[Einstellung] = []
    zeiten: list[Zeit] = []

    for gruppe in _gruppieren(norm, _bausteine(norm)):
        arten = {a for a, _ in gruppe}
        hat_speed = bool(arten & SPEED_TYPEN)
        hat_zeit = "zeit" in arten
        hat_temp = bool(arten & {"temp", "varoma"})
        start = gruppe[0][1].start()
        ende = gruppe[-1][1].end()
        fenster = norm[max(0, start - OFEN_FENSTER) : ende + OFEN_FENSTER]

        ist_einstellung = hat_speed or (hat_zeit and (hat_temp or "links" in arten))
        if ist_einstellung and not hat_speed and OFEN_WORTE.search(fenster):
            ist_einstellung = False  # Zeit + Temperatur ohne Stufe in Ofen-Umgebung: kein Mixtopf

        if not ist_einstellung:
            zeiten.extend(_zeit_aus(norm, ab) for ab in gruppe if ab[0] == "zeit")
            continue

        werte: dict = {}
        for art, m in gruppe:
            if art == "zeit":
                dauer, maximum = _dauer(m)
                werte["dauer_s"], werte["dauer_max_s"] = dauer, maximum
                if m.group("wdh"):
                    werte["wiederholungen"] = int(m.group("wdh"))
            elif art == "temp":
                t = TEMP_RE.match(m.group("temp"))
                unten = _zahl(t.group("a"))
                oben = _zahl(t.group("b")) if t.group("b") else None
                werte["temperatur_c"] = unten
                werte["temperatur_max_c"] = oben if oben not in (None, unten) else None
            elif art == "varoma":
                werte["varoma"] = True
            elif art == "stufe":
                werte["art"] = "stufe"
                werte["stufe"] = _zahl(m.group("s1"))
                if m.group("s2") and _zahl(m.group("s2")) != werte["stufe"]:
                    werte["stufe_max"] = _zahl(m.group("s2"))
            elif art == "sanft":
                werte["art"] = "sanftruehr"
            elif art == "teig":
                werte["art"] = "teigknet"
            elif art == "turbo":
                werte["art"] = "turbo"
            elif art == "links":
                werte["linkslauf"] = True

        ende_text = start + len(norm[start:ende].rstrip())
        einstellungen.append(Einstellung(text=text[start:ende_text], start=start, ende=ende_text, **werte))

    return SchrittErgebnis(einstellungen=einstellungen, zeiten=zeiten)

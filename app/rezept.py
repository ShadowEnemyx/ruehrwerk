"""Wandelt ein Mealie-Rezept (JSON, camelCase) in die Form um, die der Kochmodus braucht.

Reine Funktion ohne Netzwerk und Datenbank – deshalb leicht testbar.
"""

from dataclasses import asdict

from .parser.plausi import pruefe
from .parser.thermomix import parse_schritt

# Felder, die der Nutzer beim Bestätigen/Korrigieren ändern darf
WERTE_FELDER = ("dauer_s", "temperatur_c", "varoma", "stufe", "art", "linkslauf", "wiederholungen")


def _einheit(zutat: dict) -> str:
    einheit = zutat.get("unit") or {}
    if einheit.get("useAbbreviation") and einheit.get("abbreviation"):
        return einheit["abbreviation"]
    return einheit.get("name") or ""


def _zutat(z: dict) -> dict:
    food = z.get("food") or {}
    menge = z.get("quantity")
    return {
        "id": z.get("referenceId"),
        "titel": z.get("title") or "",
        "anzeige": (z.get("display") or z.get("originalText") or "").strip(),
        "menge": menge if isinstance(menge, (int, float)) and menge > 0 else None,
        "einheit": _einheit(z),
        "name": food.get("name") or "",
        "notiz": (z.get("note") or "").strip(),
    }


def _portionen(rezept: dict) -> float | None:
    for feld in ("recipeServings", "recipeYieldQuantity"):
        wert = rezept.get(feld)
        if isinstance(wert, (int, float)) and wert > 0:
            return wert
    return None


KI_HINWEIS = {
    "code": "KI_GELESEN",
    "text": "Von der KI aus einem Foto gelesen. Bitte Zeit, Temperatur und Stufe mit dem Foto vergleichen.",
}


def aufbereiten(
    rezept: dict, bestaetigungen: dict[tuple[str, int], dict] | None = None, ki_gelesen: bool = False
) -> dict:
    """Bereitet ein Mealie-Rezept auf.

    bestaetigungen: {(schritt_id, nr): {"quelle": str, "werte": dict}} aus der Datenbank.
    Eine Bestätigung gilt nur, solange der Originaltext der Einstellung unverändert ist.
    ki_gelesen: Das Rezept wurde per KI aus einem Foto gelesen. Dann kann auch ein plausibler Wert falsch gelesen sein
    (z. B. 6 statt 8 Min.): Jede Einstellung muss einmal bestätigt werden, nichts wird still übernommen.
    """
    bestaetigungen = bestaetigungen or {}
    schritte = []
    offen = 0
    for index, s in enumerate(rezept.get("recipeInstructions") or []):
        schritt_id = str(s.get("id") or index)
        text = s.get("text") or ""
        ergebnis = parse_schritt(text)
        einstellungen = []
        for nr, e in enumerate(ergebnis.einstellungen):
            hinweise = [{"code": h.code, "text": h.text} for h in pruefe(e)]
            if ki_gelesen:
                hinweise.append(dict(KI_HINWEIS))
            roh = asdict(e)
            gespeichert = bestaetigungen.get((schritt_id, nr))
            bestaetigt = gespeichert if gespeichert and gespeichert["quelle"] == e.text else None
            if bestaetigt:
                status = "bestaetigt"
                roh.update({k: v for k, v in bestaetigt["werte"].items() if k in WERTE_FELDER})
            elif hinweise:
                status = "pruefen"
                offen += 1
            else:
                status = "ok"
            einstellungen.append({"nr": nr, **roh, "hinweise": hinweise, "status": status})
        schritte.append(
            {
                "id": schritt_id,
                "titel": s.get("title") or "",
                "text": text,
                "zutaten": [r.get("referenceId") for r in s.get("ingredientReferences") or []],
                "einstellungen": einstellungen,
                "zeiten": [asdict(z) for z in ergebnis.zeiten],
            }
        )
    return {
        "id": rezept.get("id"),
        "slug": rezept.get("slug"),
        "name": rezept.get("name") or "",
        "beschreibung": rezept.get("description") or "",
        "portionen": _portionen(rezept),
        "hat_bild": bool(rezept.get("image")),
        "zutaten": [_zutat(z) for z in rezept.get("recipeIngredient") or []],
        "schritte": schritte,
        "offen": offen,
        "ki_gelesen": ki_gelesen,
    }

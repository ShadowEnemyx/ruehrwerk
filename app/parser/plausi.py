"""Plausibilitätsprüfung: markiert unsichere oder verdächtige Werte, statt sie still zu übernehmen.

WICHTIG: Alle Grenzwerte stehen unten in `GRENZEN`. Sie sind Faustwerte nach bestem Wissen und
müssen noch vom Projektinhaber bestätigt bzw. an einem echten Gerät geprüft werden. Ein Hinweis bedeutet nie
"falsch", sondern "bitte kurz ansehen und per Tippen bestätigen".
"""

from dataclasses import dataclass

from .modell import Einstellung


@dataclass(frozen=True)
class Hinweis:
    code: str  # stabiler Kurzname, z. B. "STUFE_FEHLT" (für Oberfläche und Tests)
    text: str  # verständlicher deutscher Text


@dataclass(frozen=True)
class Grenzen:
    # Zulässige Temperaturen: 37 °C und 40–120 °C in 5er-Schritten (Annahme, noch zu bestätigen)
    temperaturen: frozenset = frozenset({37, *range(40, 125, 5)})
    # Zulässige Stufen: 0,5 und 1–10 (Annahme, noch zu bestätigen)
    stufen: frozenset = frozenset({0.5, *range(1, 11)})
    # "Heiß": über dieser Temperatur (oder Varoma) gelten hohe Stufen als ungewöhnlich
    heiss_ab_c: float = 60
    # "Hohe Stufe": ab dieser Stufe
    hohe_stufe_ab: float = 7
    # Linkslauf (schonendes Rühren) ist normalerweise langsam: darüber ungewöhnlich
    linkslauf_max_stufe: float = 4
    # Zeiten über dieser Dauer (60 Min.) werden zur Kontrolle markiert
    lange_zeit_ab_s: float = 3600


GRENZEN = Grenzen()


def _fmt_zeit(sekunden: float) -> str:
    if sekunden >= 60 and sekunden % 60 == 0:
        return f"{int(sekunden // 60)} Min."
    return f"{sekunden:g} Sek."


def pruefe(e: Einstellung, grenzen: Grenzen = GRENZEN) -> list[Hinweis]:
    """Gibt alle Auffälligkeiten einer Einstellung zurück (leere Liste = unauffällig)."""
    h: list[Hinweis] = []
    heiss = e.varoma or (e.temperatur_c is not None and e.temperatur_c > grenzen.heiss_ab_c)

    # --- Bereiche: der Nutzer muss sich entscheiden ---
    if e.dauer_max_s is not None:
        h.append(Hinweis("BEREICH_ZEIT", f"Im Rezept steht ein Zeitbereich ({e.text}). Bitte den Wert wählen."))
    if e.temperatur_max_c is not None:
        h.append(Hinweis("BEREICH_TEMP", f"Im Rezept steht ein Temperaturbereich ({e.text}). Bitte den Wert wählen."))
    if e.stufe_max is not None:
        h.append(Hinweis("BEREICH_STUFE", f"Im Rezept steht ein Stufenbereich ({e.text}). Bitte den Wert wählen."))

    # --- Fehlende Angaben ---
    hat_gerätewerte = e.art != "keine" or e.temperatur_c is not None or e.varoma
    if e.dauer_s is None and hat_gerätewerte:
        h.append(Hinweis("ZEIT_FEHLT", "Im Rezept steht keine Zeit. Bitte prüfen, wie lange es laufen soll."))
    if e.art == "keine" and (e.dauer_s is not None):
        h.append(Hinweis("STUFE_FEHLT", "Im Rezept steht keine Stufe. Bitte prüfen, welche Stufe gemeint ist."))

    # --- Werte außerhalb dessen, was das Gerät kann ---
    if e.temperatur_c is not None and e.temperatur_c not in grenzen.temperaturen:
        h.append(
            Hinweis("TEMP_UNGUELTIG", f"{e.temperatur_c:g} °C lässt sich am Gerät nicht einstellen. Bitte prüfen.")
        )
    if e.stufe is not None and e.stufe not in grenzen.stufen:
        h.append(Hinweis("STUFE_UNGUELTIG", f"Stufe {e.stufe:g} gibt es nicht (0,5 oder 1–10). Bitte prüfen."))
    if e.dauer_s is not None and e.dauer_s <= 0:
        h.append(Hinweis("ZEIT_UNGUELTIG", "Die Zeit ist 0. Bitte prüfen."))
    elif e.dauer_s is not None and e.dauer_s > grenzen.lange_zeit_ab_s:
        h.append(Hinweis("ZEIT_LANG", f"Die Zeit ist sehr lang ({_fmt_zeit(e.dauer_s)}). Bitte prüfen."))

    # --- Ungewöhnliche Kombinationen ---
    if heiss and e.stufe is not None and e.stufe >= grenzen.hohe_stufe_ab:
        h.append(Hinweis("HEISS_SCHNELL", f"Hohe Stufe ({e.stufe:g}) bei heißem Inhalt ist ungewöhnlich. Bitte prüfen."))
    if e.linkslauf and e.stufe is not None and e.stufe > grenzen.linkslauf_max_stufe:
        h.append(Hinweis("LINKSLAUF_SCHNELL", f"Linkslauf mit Stufe {e.stufe:g} ist ungewöhnlich. Bitte prüfen."))
    if e.art == "turbo" and (e.temperatur_c is not None or e.varoma):
        h.append(Hinweis("TURBO_MIT_TEMP", "Turbo zusammen mit einer Temperatur ist ungewöhnlich. Bitte prüfen."))
    if e.art == "teigknet" and (e.temperatur_c is not None or e.varoma):
        h.append(Hinweis("TEIG_MIT_TEMP", "Teigknetstufe zusammen mit einer Temperatur ist ungewöhnlich. Bitte prüfen."))

    return h

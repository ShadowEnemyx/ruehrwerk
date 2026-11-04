"""Datenmodell für erkannte Gerät-Einstellungen. Reine Python-Klassen ohne Abhängigkeiten."""

from dataclasses import dataclass, field

# Art der Drehzahl:
#   "stufe"      -> normale Stufe (Zahl in `stufe`)
#   "sanftruehr" -> Sanftrührstufe
#   "teigknet"   -> Teigknetstufe
#   "turbo"      -> Turbo
#   "keine"      -> im Text steht keine Drehzahl
ARTEN = ("stufe", "sanftruehr", "teigknet", "turbo", "keine")


@dataclass(frozen=True)
class Einstellung:
    """Eine Einstellung wie "3 Min./100°C/Stufe 1" aus einem Rezeptschritt."""

    text: str  # Originaltext aus dem Rezept
    start: int  # Position im Schritttext (Anfang)
    ende: int  # Position im Schritttext (Ende, exklusiv)
    dauer_s: float | None = None
    dauer_max_s: float | None = None  # nur gesetzt, wenn der Text einen Bereich nennt ("2-3 Min.")
    temperatur_c: float | None = None
    temperatur_max_c: float | None = None
    varoma: bool = False
    stufe: float | None = None
    stufe_max: float | None = None
    art: str = "keine"
    linkslauf: bool = False
    wiederholungen: int = 1


@dataclass(frozen=True)
class Zeit:
    """Eine einfache Zeitangabe ohne Geräteeinstellung ("30 Min. ruhen lassen") – gut für einen Timer."""

    text: str
    start: int
    ende: int
    dauer_s: float
    dauer_max_s: float | None = None


@dataclass(frozen=True)
class SchrittErgebnis:
    einstellungen: list[Einstellung] = field(default_factory=list)
    zeiten: list[Zeit] = field(default_factory=list)

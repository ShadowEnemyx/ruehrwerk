"""Kleine SQLite-Datenbank für die vom Nutzer bestätigten Einstellungen.

Warum eine eigene Datei und nicht Mealie? Mealie bleibt unverändert und unser Modul unabhängig.
"""

import json
import sqlite3
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS bestaetigung (
    slug         TEXT    NOT NULL,
    schritt_id   TEXT    NOT NULL,
    nr           INTEGER NOT NULL,
    quelle       TEXT    NOT NULL,
    werte        TEXT    NOT NULL,
    bestaetigt_am TEXT   NOT NULL,
    PRIMARY KEY (slug, schritt_id, nr)
)
"""


class Speicher:
    def __init__(self, ordner: Path):
        ordner.mkdir(parents=True, exist_ok=True)
        self._datei = ordner / "ruehrwerk.sqlite3"
        with closing(self._verbinden()) as db, db:
            db.execute(SCHEMA)

    def _verbinden(self) -> sqlite3.Connection:
        return sqlite3.connect(self._datei, timeout=10)

    def laden(self, slug: str) -> dict[tuple[str, int], dict]:
        with closing(self._verbinden()) as db:
            zeilen = db.execute(
                "SELECT schritt_id, nr, quelle, werte FROM bestaetigung WHERE slug = ?", (slug,)
            ).fetchall()
        return {(sid, nr): {"quelle": quelle, "werte": json.loads(werte)} for sid, nr, quelle, werte in zeilen}

    def bestaetigen(self, slug: str, schritt_id: str, nr: int, quelle: str, werte: dict) -> None:
        jetzt = datetime.now(UTC).isoformat(timespec="seconds")
        with closing(self._verbinden()) as db, db:
            db.execute(
                "INSERT OR REPLACE INTO bestaetigung (slug, schritt_id, nr, quelle, werte, bestaetigt_am) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (slug, schritt_id, nr, quelle, json.dumps(werte), jetzt),
            )

    def zuruecknehmen(self, slug: str, schritt_id: str, nr: int) -> None:
        with closing(self._verbinden()) as db, db:
            db.execute(
                "DELETE FROM bestaetigung WHERE slug = ? AND schritt_id = ? AND nr = ?", (slug, schritt_id, nr)
            )

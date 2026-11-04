# Projektregeln

Self-hosted Begleit-App für Thermomix®-Besitzer ohne Cookidoo-Abo, als eigener Dienst neben Mealie.
Arbeitstitel; der endgültige Projektname wird noch festgelegt.

## Zusammenarbeit
- Nutzer: Hobby-Entwickler (GitHub `ShadowEnemyx`). Alles auf Deutsch, Schritt für Schritt erklären.
- Bei jedem Befehl kurz sagen, was er tut.
- Nie raten: API-Endpunkte, Versionen und Befehle in der aktuellen Doku oder im Quellcode prüfen, sonst offen sagen.
- Vor größeren Architekturentscheidungen nachfragen. Abweichungen vom festgelegten Stack erst begründen, dann umsetzen.
- Arbeit in Meilensteinen (M1–M4). Jeder Meilenstein wird getestet, bevor der nächste beginnt.
- Kleine, nachvollziehbare Commits. Die README ist auf Deutsch und wächst mit.

## Architektur (festgelegt)
- Mealie (aktuelle stabile Version) bleibt unverändert. Unser Modul spricht nur über die offizielle
  Mealie-REST-API mit API-Token. Endpunkte vor der Nutzung gegen Doku/Quellcode der eingesetzten Version prüfen.
- Zielsystem: Proxmox VE 8.2.2 (muss dort laufen, nicht erst ab 8.4), Intel N100, 16 GB RAM.
  Installation in einen NEUEN Debian-12-LXC. Bestehende Container nie anfassen.
- Stack: Python 3.11 (Debian-12-Standard) + FastAPI. Frontend: schlanke PWA mit möglichst wenigen Abhängigkeiten.
- Muss auf iPhone (Safari) und Android (Chrome) funktionieren.
- Der Thermomix wird nicht angesteuert oder verändert. Das Modul ist eine Begleit-App auf Handy/Tablet.

## Funktionen
1. Link-Import über Mealie (schema.org/Recipe), danach Aufbereitung der Schritte. Ohne KI.
2. Thermomix-Parser für deutsche Rezepttexte: Zeit, Temperatur, Stufe, Sonderangaben
   (Linkslauf, Sanftrührstufe, Varoma, Teigknetstufe, Stufe 0,5, Schreibvarianten). Umfangreiche Unit-Tests.
3. Plausibilitätsprüfung: unsichere/verdächtige Werte markieren, nie still übernehmen. Bestätigen per Tippen.
4. Kochmodus-PWA: ein Schritt pro Bildschirm, große Schrift, Timer, Wake Lock, Portionen umrechnen.
5. Teilen: Android per Web Share Target, iPhone per Apple-Kurzbefehl.
6. Optionaler Foto-Import über OpenAI-kompatible API. Ohne Schlüssel funktioniert alles außer Foto-Import.
7. Ein-Klick-Installation per Bash-Script im Stil der community-scripts, plus Laien-Anleitung.

## Meilensteine
- M1: Projektgerüst, Mealie-Anbindung, Parser mit Tests, Kochmodus-PWA (manuelle Installation).
- M2: Teilen-Funktion Android und iPhone-Kurzbefehl.
- M3: Foto-Import mit Schlüssel-Assistent.
- M4: Installationsscript und Laien-Anleitung.

## Rechtliche Leitplanken
- „Thermomix“ und „Cookidoo“ sind Marken von Vorwerk: nie im Projektnamen, Logo, Paketnamen oder in der
  Domain verwenden. In Beschreibungen höchstens „kompatibel mit Thermomix®“.
- Kein Zugriff auf Cookidoo, kein Umgehen von Schutzmaßnahmen.
- Importierte Rezepte nur für den privaten Gebrauch. Keine Funktion zum Teilen oder Veröffentlichen fremder Rezepte.

## Sicherheit
- API-Schlüssel und Tokens (Mealie, OpenAI) nie in Code, Logs, Commits oder Antworten ausgeben.
  Nur in lokaler Konfiguration bzw. Einstellungsseite speichern; `.env` gehört in `.gitignore`.

<!-- skill-routing:start v2 – gepflegt mit ~/.claude/skill-routing/skill_routing.py; gemeinsame Regeln in AGENTS.md; CLAUDE.md bindet sie ein -->
## Skill-Zuordnung

Projektart: Web-Projekt.

| Wann | Skill |
| --- | --- |
| Weboberfläche im Browser prüfen: klicken, Formulare, Screenshots, Konsolenfehler | `playwright` |
| Backend/API-Design, Datenbankschema, Migrationen, Auth, Architekturentscheidungen | `fullstack-architecture` |
| Oberfläche bauen oder prüfen: Zustände, responsives Layout, Barrierefreiheit, Formulare, Dunkelmodus | `ui-ux-quality` |
| Nur auf ausdrücklichen Wunsch: fremde App analysieren oder nachbauen | `replica-*` (Start: `replica-recon`) |

Nicht zuständig: `apple-app-release-check` (keine App-Store-App).

Skills nur verwenden, wenn die Aufgabe dazu passt; die globale Regel gilt zusätzlich.
In Claude Code heißen die Plugin-Skills `swiftui-expert:swiftui-expert-skill` und `swift-concurrency:swift-concurrency`.
<!-- skill-routing:end -->

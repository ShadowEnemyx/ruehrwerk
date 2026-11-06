# Status Rührwerk

Stand: 06.11.2026. Repository: https://github.com/ShadowEnemyx/ruehrwerk. Letzter Commit auf GitHub: `c48946b`; lokal liegen darüber nur Dokumentations-Commits (siehe "Commits").

## Zusammenfassung
M1 (Gerüst, Mealie-Anbindung, Parser, Kochmodus) und M3 (Foto-/Text-Import per KI über Mealie) sind umgesetzt und laufen auf dem Proxmox-Server des Projektinhabers; am Handy getestet. M4 ist teilweise da (Installer, Laien-Anleitung). M2 (Teilen vom Handy) ist nicht begonnen.

## Was läuft (Betrieb)
- Proxmox VE 8.2.2, Host `pve`, Container 112 (`ruehrwerk`, Debian 12, unprivilegiert, Speicher `local-lvm`).
- Im Container: Docker mit Mealie v3.30.0 (Port 9000) und Rührwerk (Port 8080), Dateien in `/opt/ruehrwerk` (Quellcode in `quelle`).
- Installer lief am 05.11.2026 erfolgreich durch; Rührwerk meldet "mit Mealie verbunden".
- Auf dem Server läuft der Stand von `c48946b` (laut Projektinhaber aktualisiert und getestet).
- `lxc-pve` ist 6.0.0-2 (älter als 6.0.5-2). Docker lief trotzdem; ob der Installer containerd festgesetzt hat, ist nicht dokumentiert. Proxmox-Update steht aus.
- Update im Container-Terminal (`pct enter 112`, dort ohne `pct exec`):
  `cd /opt/ruehrwerk && curl -fsSL https://github.com/ShadowEnemyx/ruehrwerk/archive/refs/heads/main.tar.gz | tar -xz --strip-components=1 -C quelle && docker compose up -d --build ruehrwerk`
  Vom Proxmox-Host aus: derselbe Befehl als `pct exec 112 -- bash -c '…'`.
- Container-Konsole: Benutzer `root`, der Installer setzt kein Passwort; Zugang über `pct enter 112`. Der Projektinhaber hat später selbst ein Passwort gesetzt.

## Funktionen (Stand)
- Link-Import über Mealie, Aufbereitung der Schritte ohne KI.
- Thermomix-Parser (Zeit, Temperatur, Stufe, Linkslauf, Sanftrühr-, Teigknetstufe, Varoma, Turbo, Bereiche). Aus echten Rezepten ergänzt: `St.`/`St` für Stufe, `100 C` ohne Gradzeichen, `sec`/`Sec` als Sekunden.
- Plausibilitätsprüfung (`app/parser/plausi.py`), Bestätigungen per Tippen in SQLite; Hinweise mit Dezimalkomma.
- Kochmodus: ein Schritt pro Bildschirm, Timer, Portionen umrechnen. Bildschirm bleibt an: über HTTPS mit Wake Lock, über `http://` mit unsichtbarem stummem Video (Start per Berührung, Statusanzeige im Kochmodus).
- Foto-/Text-Import per KI (M3): Fotos (JPEG/PNG/WebP/GIF, höchstens 6 je 10 MB), optionaler Text und/oder Link an Mealies `POST /api/recipes/create/ai` (im Quellcode v3.30.0 gelesen). Route `/api/import-ki`, Reiter "Link" / "Foto / Text". Rührwerk speichert die Fotos nicht; sie gehen über Mealie an den KI-Anbieter. Mealie-Fehlertexte werden angezeigt. Neue Abhängigkeit: `python-multipart`.
- KI-gelesene Rezepte: Wurde ein Rezept per Foto importiert, merkt sich Rührwerk das (SQLite-Tabelle `ki_rezept`). Jede Einstellung steht dann auf "prüfen" und braucht einmal "Passt so" oder "Ändern"; gelber Hinweis oben im Rezept. "Ändern" gibt es im Kochmodus auch bei unauffälligen Werten. Reine Text-Importe werden nicht markiert.
- Links zu Cookidoo werden mit Hinweis abgelehnt (Projektregel: kein Cookidoo-Zugriff).
- Rezeptbild oben wird vollständig gezeigt (`object-fit: contain`).

## Geprüft (datiert)
- 06.11.2026: 212 automatische Tests grün (Parser, Plausibilität, Mealie-Client, API inkl. KI-Import und Cookidoo-Ablehnung, Aufbereitung inkl. KI-Markierung, Installer inkl. Trockenlauf mit nachgestellten Proxmox-Befehlen).
- 06.11.2026: Oberfläche für Foto-/Text-Import, KI-Hinweis und Cookidoo-Meldung im Browser gegen ein nachgestelltes Mealie (`tools/fake_mealie.py`) gesehen (Handybreite).
- Laut Projektinhaber, 06.11.2026: Foto-Import mit echter KI funktioniert; ein handgeschriebenes Rezept ("Salatsoße") wird nach dem `sec`-Fix vollständig erkannt; Wachhalten am iPhone funktioniert.
- 05.11.2026: Trockenlauf und echter Lauf des Installers; Import echter Rezepte (rezeptwelt.de); Parser-Erkennung von `5 Sek/St. 5`, `2min/100 C/St. 1`, `5min/100 C/ St. 2,5` im Safari gegen den laufenden Server; Dezimalkomma im Hinweis am Handy.

## Nicht geprüft / Einschränkungen
- KI-Qualität über mehrere Rezepte, mehrseitige Fotos, HEIC-Fotos, Zeitlimit 240 s bei sehr langsamer KI. Die KI-Markierung (gelber Hinweis, Prüfliste) habe ich nur gegen ein nachgestelltes Mealie gesehen; eine Rückmeldung vom echten System mit einem neu importierten Foto-Rezept steht aus.
- Die KI kann Zahlen falsch lesen (Beispiel: "6 min" als "8 min"); die Plausibilitätsprüfung kann das nicht erkennen. Gegenmaßnahme ist die Prüfpflicht bei Foto-Rezepten. Einfache Timer-Zeiten im Text (ohne Geräte-Einstellung, z. B. "20 Min. ruhen lassen") werden nicht markiert.
- Der Parser kennt nur das, was in Tests steht: weitere Schreibweisen tauchen erst mit echten Rezepten auf.
- Android: Wachhalten und Kochmodus ungetestet.
- Plausibilitätsgrenzen (`GRENZEN` in `app/parser/plausi.py`) sind Annahmen: Temperaturen 37 °C und 40–120 °C in 5er-Schritten, Stufen 0,5 und 1–10. Nicht am echten Gerät bestätigt (Stufe 2,5 wird als "prüfen" markiert).
- Service Worker, Offline-Betrieb und "Als App installieren" brauchen HTTPS; über `http://` nicht nutzbar.
- Dockerfile auf dem Entwicklungsrechner nicht gebaut (Docker Desktop dort nicht nutzbar); gebaut wurde es im Container 112.
- Der Sicherheitscheck des Plugins `security-guidance` lief bei den letzten Commits nicht (Anmeldung abgelehnt, HTTP 401); die Commits seit `fec5fe9` wurden nicht automatisch geprüft. Protokoll: `~/.claude/security/log.txt`.

## Bekannte Punkte aus Tests mit echten Rezepten
- Quellen, die Schritte nur Mitgliedern zeigen (z. B. ein rezeptwelt.de-Rezept), liefern in Mealie nur den Platzhaltertext "Recipe steps as well as other fields …". Rührwerk zeigt dann einen verwirrenden englischen Satz statt eines klaren Hinweises. Verbesserung geplant, nicht umgesetzt.
- Rezepte, die vor der KI-Markierung importiert wurden, sind nicht als "KI-gelesen" gemerkt.

## Entscheidungen
- Name Rührwerk, öffentliches Repository, SQLite für Bestätigungen, Mealie und Rührwerk in einem Container, Docker im LXC.
- Mealie-Standardpasswort vom Projektinhaber am 05.11.2026 geändert (laut seiner Aussage, nicht von mir geprüft). Mealie-KI-Anbieter (GPT mini) vom Projektinhaber eingetragen; "Connection successful / Supports images" gemeldet. API-Schlüssel gehören nur in Mealie.
- "Öffentlicher Zugriff" in Mealie: empfohlen aus (private Nutzung fremder Rezepte).
- Foto-Import läuft über Mealies KI statt über einen eigenen OpenAI-Zugang in Rührwerk (kein Schlüssel-Assistent nötig).
- Kein Cookidoo-Import (Projektregel); stattdessen frei zugängliche Links, Fotos eigener Kochbücher oder Text.
- HTTPS: kein Reverse-Proxy. Tailscale nur als spätere Option (nicht im Installer); WireGuard der Fritzbox löst HTTPS nicht. Kochen findet meist zuhause statt.

## Offene Punkte
1. Android testen (Kochmodus, Wachhalten).
2. Hinweis "Keine Zubereitungsschritte gefunden" statt des Mealie-Platzhalters.
3. Plausibilitätsgrenzen am Gerät bestätigen (u. a. Stufe 2,5).
4. Proxmox aktualisieren (`apt update && apt dist-upgrade`), danach `apt-mark unhold containerd.io` im Container, falls festgesetzt; vorher Sicherung/Snapshot.
5. Entscheiden, ob ein Knopf "Alle bestätigen" für KI-Rezepte nötig ist (Rückmeldung des Projektinhabers steht aus).
6. Geräte der Nutzer klären (iPhone/Android) für M2.
7. Optional: Anmeldung des Sicherheits-Plugins erneuern.

## Nächste Schritte
- Mehr echte Rezepte importieren (Links, Fotos); falsch gelesene Sätze als Tests aufnehmen.
- M2: Teilen-Funktion. iPhone per Apple-Kurzbefehl (braucht kein HTTPS), Android per Web Share Target (braucht HTTPS, z. B. über Tailscale).
- M4: Installer um optionales Tailscale ergänzen, Anleitung weiter verfeinern (Foto-Import, KI-Einrichtung in Mealie).
- Optional: `PROJECT_CONTEXT.md` für dauerhafte Technik und Schutzregeln anlegen (existiert noch nicht).

## Commits (neueste zuerst)
- `c48946b` Parser: sec/Sec als Sekunden erkennen (letzter Stand auf GitHub)
- `4cdad1d` KI-gelesene Rezepte: alle Einstellungen zur Bestätigung markieren, Ändern auch bei unauffälligen Werten
- `3788349` Rezeptbild vollständig anzeigen (contain)
- `3fe3630` Foto-/Text-Import per KI über Mealie, Cookidoo-Hinweis, Reiter
- `d241a57` Wachhalten am iPhone: Video bei Berührung starten, Status anzeigen
- `fec5fe9` Kochmodus: Bildschirm ohne HTTPS per stummem Video wachhalten
- `f40ca40` Plausibilitätshinweise: Dezimalkomma statt Punkt
- `bd9d666` Parser: St. als Stufe und 100 C ohne Gradzeichen erkennen
- `4ff63f6` Installer für Proxmox, Dockerfile, Anleitung
- Darüber lokal nur STATUS.md-Änderungen (nicht gepusht).

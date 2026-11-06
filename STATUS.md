# Status Rührwerk

Stand: 05.11.2026. Letzter Commit auf GitHub: `fec5fe9`. Repository: https://github.com/ShadowEnemyx/ruehrwerk

## Zusammenfassung
M1 ist umgesetzt und auf dem echten System in Betrieb: Installation per Einzeiler, Import über Mealie, Parser mit Plausibilitätsprüfung und Kochmodus laufen auf dem Proxmox-Server und wurden am Handy getestet. M2 bis M4 sind nicht abgeschlossen (M4 teilweise: Installer und Anleitung existieren).

## Was läuft (Betrieb)
- Proxmox VE 8.2.2, Host `pve`, Container 112 (`ruehrwerk`, Debian 12, unprivilegiert, Speicher `local-lvm`).
- Im Container: Docker mit Mealie v3.30.0 (Port 9000) und Rührwerk (Port 8080), Dateien in `/opt/ruehrwerk` (Quellcode in `quelle`).
- Installer lief am 05.11.2026 erfolgreich durch; Rührwerk meldet "mit Mealie verbunden".
- `lxc-pve` ist 6.0.0-2 (älter als 6.0.5-2). Der Installer hat den Docker-Selbsttest dafür vorgesehen; Proxmox-Update steht aus.
- Update-Befehl für den Container (Quellcode neu laden, nur Rührwerk neu bauen):
  `pct exec 112 -- bash -c 'cd /opt/ruehrwerk && curl -fsSL https://github.com/ShadowEnemyx/ruehrwerk/archive/refs/heads/main.tar.gz | tar -xz --strip-components=1 -C quelle && docker compose up -d --build ruehrwerk'`

## Geprüft (datiert)
- 05.11.2026: 196 automatische Tests grün (Parser, Plausibilität, Mealie-Client, API, Installer inkl. Trockenlauf mit nachgestellten Proxmox-Befehlen).
- 05.11.2026: Trockenlauf und echter Lauf des Installers auf dem Proxmox des Projektinhabers.
- 05.11.2026: Import echter Rezepte (rezeptwelt.de) in Rührwerk über Mealie; Kochmodus am Handy "sieht gut aus" (Aussage des Projektinhabers).
- 05.11.2026: Parser-Erkennung von `5 Sek/St. 5`, `2min/100 C/St. 1`, `5min/100 C/ St. 2,5` im Safari des Projektinhabers gegen den laufenden Server geprüft; Prüfhinweis "Stufe 2,5 gibt es nicht" erscheint, Dezimalkomma im Hinweis am Handy bestätigt.

## Nicht geprüft / Einschränkungen
- Ersatz fürs Wachhalten ohne HTTPS (stummes Video, `web/wach.mp4`/`wach.webm`): eingebaut und ausgeliefert, aber **ob der Bildschirm am iPhone bzw. Android tatsächlich anbleibt, ist offen**.
- Docker-Ausweichweg (containerd festsetzen) wurde auf dem echten System nicht bewusst ausgelöst/ausgewertet; Version und Zustand im Container nicht dokumentiert.
- Dockerfile auf dem Entwicklungsrechner nicht gebaut (Docker Desktop dort nicht nutzbar); gebaut wurde es nur im Container 112.
- Plausibilitätsgrenzen (`GRENZEN` in `app/parser/plausi.py`) sind Annahmen: Temperaturen 37 °C und 40–120 °C in 5er-Schritten, Stufen 0,5 und 1–10. Nicht am echten Gerät bestätigt (Stufe 2,5 wird daher als "prüfen" markiert).
- Service Worker / Offline und "Als App installieren" brauchen HTTPS; über `http://` nicht nutzbar.
- Mealie-KI-Anbieter (GPT mini): vom Projektinhaber in Mealies Einrichtungsassistent eingetragen; Verbindungstest und Funktion von mir nicht gesehen. API-Schlüssel gehören nur in Mealie.

## Bekannte Punkte aus Tests mit echten Rezepten
- Quellen, die Schritte nur Mitgliedern zeigen (z. B. ein rezeptwelt.de-Rezept), liefern in Mealie nur den Platzhaltertext "Recipe steps as well as other fields …". Rührwerk zeigt dann einen verwirrenden englischen Satz statt eines klaren Hinweises. Verbesserung ist geplant, noch nicht umgesetzt.
- Schreibweisen aus echten Rezepten wurden ergänzt: `St.`/`St` für Stufe, `100 C` ohne Gradzeichen. Weitere Schreibvarianten werden nur aus echten Beispielsätzen als Tests aufgenommen.

## Entscheidungen
- Name Rührwerk, öffentliches Repository, SQLite für Bestätigungen, Mealie und Rührwerk in einem Container, Docker im LXC.
- Mealie-Standardpasswort: vom Projektinhaber am 05.11.2026 geändert (laut seiner Aussage, nicht von mir geprüft).
- "Öffentlicher Zugriff" in Mealie: empfohlen aus, wegen privater Nutzung fremder Rezepte.
- HTTPS: kein Reverse-Proxy. Tailscale nur als spätere Option (noch nicht im Installer); WireGuard der Fritzbox löst HTTPS nicht. Kochen findet meist zuhause statt.

## Offene Punkte
1. Handy-Test Bildschirm-Wachhalten (iPhone und Android getrennt).
2. Hinweis "Keine Zubereitungsschritte gefunden" statt des Mealie-Platzhalters.
3. Plausibilitätsgrenzen am Gerät bestätigen (u. a. Stufe 2,5).
4. Proxmox aktualisieren (`apt update && apt dist-upgrade`), danach `apt-mark unhold containerd.io` im Container falls festgesetzt; vorher Sicherung/Snapshot.
6. Nutzer-Geräte klären (iPhone/Android) für M2.

## Nächste Schritte
- M2: Teilen-Funktion. iPhone per Apple-Kurzbefehl (braucht kein HTTPS), Android per Web Share Target (braucht HTTPS, z. B. über Tailscale).
- M3: Foto-Import über OpenAI-kompatible API mit Schlüssel-Assistent. Prüfen, ob Mealies eigene "Mit KI importieren"-Funktion (Fotos) genutzt werden kann, statt einen eigenen Weg zu bauen.
- M4: Installer um optionales Tailscale ergänzen, Anleitung weiter verfeinern.
- Mehr echte Rezepte importieren, falsch gelesene Sätze als Tests aufnehmen.
- Optional: `PROJECT_CONTEXT.md` für dauerhafte Technik und Schutzregeln anlegen (existiert noch nicht).

## Commits (neueste zuerst)
- `fec5fe9` Kochmodus: Bildschirm ohne HTTPS per stummem Video wachhalten
- `f40ca40` Plausibilitätshinweise: Dezimalkomma statt Punkt
- `bd9d666` Parser: St. als Stufe und 100 C ohne Gradzeichen erkennen
- `4ff63f6` Installer für Proxmox, Dockerfile, Anleitung

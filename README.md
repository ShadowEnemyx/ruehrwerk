# Rührwerk

Begleit-App für [Mealie](https://mealie.io), mit der du Rezepte mit Thermomix®-Angaben bequem am Handy oder
Tablet kochen kannst – kompatibel mit Thermomix®. Rührwerk steuert das Gerät nicht, es zeigt dir nur Schritt für
Schritt, was du einstellen musst.

> **Stand:** Meilenstein 1 in Arbeit. Noch nicht für den Alltag gedacht.

## Was es kann (Ziel)
- Rezept-Link in Mealie importieren, Schritte für den Kochmodus aufbereiten (ohne KI)
- Zeit, Temperatur und Stufe in deutschen Rezepttexten erkennen und große anzeigen
- Unsichere Werte markieren, du bestätigst sie per Tippen
- Kochmodus mit Timer, Bildschirm bleibt an, Portionen umrechnen

## Ausprobieren (Entwicklung, Mac)
```bash
python3.11 -m venv --copies .venv          # eigene Python-Umgebung (--copies wegen ExFAT)
.venv/bin/python -m pip install -e ".[dev]"
cp .env.example .env                       # Mealie-Adresse und API-Token eintragen
.venv/bin/python -m pytest                 # Tests
.venv/bin/python -m uvicorn app.main:app --port 8080
```
Ohne Mealie kannst du die Oberfläche mit dem Ersatzserver ausprobieren:
`.venv/bin/python -m uvicorn tools.fake_mealie:app --port 9000` (nur zum Testen, erfundene Rezepte).

Hinweis: Rührwerk hat noch keine eigene Anmeldung. Betreibe es nur im Heimnetz, nicht offen im Internet.

## Rechtliches
- „Thermomix“ ist eine eingetragene Marke der Vorwerk International & Co. KmG. Rührwerk ist ein unabhängiges
  Projekt und steht in keiner Verbindung zu Vorwerk.
- Rührwerk greift nicht auf Cookidoo zu. Importierte Rezepte sind nur für den privaten Gebrauch gedacht.

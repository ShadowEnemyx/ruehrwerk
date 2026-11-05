# Installation auf Proxmox (Schritt für Schritt)

> **Stand:** Der Installer ist noch nicht auf echter Proxmox-Hardware erprobt. Starte deshalb immer zuerst
> mit dem Trockenlauf (Schritt 1). Er zeigt nur an, was passieren würde, und verändert nichts.

## Was du brauchst
- Einen Proxmox-VE-Server, Version 8.x (entwickelt für 8.2.2), mit Internetzugang
- Zugriff auf die Proxmox-Shell (im Webinterface: Server auswählen → „Shell“)
- Etwa 12 GB freien Platz auf einem lokalen Speicher (kein Netzlaufwerk)

## Was der Installer macht
1. Legt einen **neuen** Container an (Debian 12). Bestehende Container und der Proxmox-Host bleiben unverändert.
2. Installiert darin Docker.
3. Startet **Mealie** (Rezeptverwaltung) und **Rührwerk** (Kochmodus).
4. Erzeugt in Mealie automatisch den Zugangsschlüssel (API-Token) und trägt ihn bei Rührwerk ein.

## Schritt 1: Trockenlauf (verändert nichts)
Diesen Befehl in die Proxmox-Shell einfügen und mit Enter bestätigen:

```bash
bash -c "$(curl -fsSL https://raw.githubusercontent.com/ShadowEnemyx/ruehrwerk/main/install/ruehrwerk.sh)" _ --trockenlauf
```

Du siehst eine Übersicht (welche Nummer, welcher Speicher, wie viel Platz) und alle geplanten Schritte.
Alles, was mit `[Trockenlauf]` beginnt, wird nur angezeigt, nicht ausgeführt.

## Schritt 2: Wirklich installieren
Derselbe Befehl, aber ohne `_ --trockenlauf`:

```bash
bash -c "$(curl -fsSL https://raw.githubusercontent.com/ShadowEnemyx/ruehrwerk/main/install/ruehrwerk.sh)"
```

Der Installer zeigt den Plan und fragt „Jetzt einrichten? [j/N]“. Mit `j` geht es los. Das dauert einige Minuten,
weil Docker und die Programme heruntergeladen werden.

Mit Optionen anpassen (Beispiele): `_ --id 120 --ip 192.168.1.50/24 --gateway 192.168.1.1 --ram 3072`.
Alle Optionen: `_ --hilfe`.

## Schritt 3: Mealie-Passwort ändern
Am Ende zeigt der Installer zwei Adressen. Öffne die von **Mealie** (Port 9000) und melde dich an:
- Benutzer: `changeme@example.com`
- Passwort: `MyPassword`

Dieser Zugang ist öffentlich bekannt. **Ändere das Passwort sofort** (Benutzerprofil → Passwort ändern)
und trage deine eigene E-Mail-Adresse ein. Betreibe die Dienste nur im Heimnetz, nicht offen im Internet.

## Schritt 4: Rührwerk benutzen
Öffne die Adresse von **Rührwerk** (Port 8080) am Handy. Oben steht „Mealie verbunden“. Füge einen Rezept-Link ein
und tippe auf „Importieren“.

**Bildschirm bleibt an:** Auch ohne HTTPS (also über `http://` im Heimnetz) hält Rührwerk den Bildschirm im
Kochmodus mit einem Ersatztrick an: Ein winziges stummes Video läuft unsichtbar mit. Das ist kein Garant, probiere es
an deinem Handy aus. Geht der Bildschirm trotzdem aus, stelle die Bildschirmsperre länger ein.

**HTTPS (optional):** Offline-Betrieb und „Als App installieren“ funktionieren nur über HTTPS, ebenso die
eingebaute Bildschirm-Sperre des Browsers. Zuhause brauchst du das nicht zwingend. Wenn du es später möchtest,
geht es zum Beispiel mit Tailscale; das ist noch nicht in den Installer eingebaut.

## Probleme
- **„Docker-Selbsttest FEHLGESCHLAGEN“ / Fehler mit `ip_unprivileged_port_start`:** Dein Proxmox ist älter als `lxc-pve 6.0.5-2`.
  Der Installer weicht automatisch auf eine ältere containerd-Version aus. Hilft das nicht, aktualisiere Proxmox
  (`apt update && apt dist-upgrade`, danach neu starten) und starte den Installer neu.
- **Der Installer bricht ab:** Er nennt den Container, der schon angelegt wurde. Entfernen mit
  `pct stop NUMMER; pct destroy NUMMER`, dann erneut starten.
- **Rührwerk meldet „Mealie nicht verbunden“:** Im Container nachsehen: `pct enter NUMMER`, dann
  `docker logs ruehrwerk` und `docker logs mealie`.

## Wieder entfernen
Löscht den Container samt allen Daten (Rezepte, Bestätigungen):

```bash
pct stop NUMMER; pct destroy NUMMER
```

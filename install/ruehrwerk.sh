#!/usr/bin/env bash
# =============================================================================
# Rührwerk – Installer für Proxmox VE
#
# Legt einen NEUEN Debian-12-Container an, installiert Docker darin, startet Mealie und
# Rührwerk und verbindet beide miteinander. Bestehende Container werden nie angefasst.
#
# Aufruf in der Proxmox-Shell (als root):
#   bash -c "$(curl -fsSL https://raw.githubusercontent.com/ShadowEnemyx/ruehrwerk/main/install/ruehrwerk.sh)"
#
# Erst nur ansehen, was passieren würde (verändert nichts):
#   bash -c "$(curl -fsSL https://raw.githubusercontent.com/ShadowEnemyx/ruehrwerk/main/install/ruehrwerk.sh)" _ --trockenlauf
#
# STAND: Auf echter Proxmox-Hardware noch nicht getestet. Bitte zuerst mit --trockenlauf starten.
# =============================================================================
set -Eeuo pipefail

INSTALLER_VERSION="0.1.0"

# ---- Voreinstellungen (alles per Option oder Umgebungsvariable änderbar) ----
MEALIE_VERSION="${MEALIE_VERSION:-v3.30.0}"
QUELLE="${RUEHRWERK_QUELLE:-https://github.com/ShadowEnemyx/ruehrwerk/archive/refs/heads/main.tar.gz}"
NAME="ruehrwerk"
KERNE=2
RAM=2048
PLATTE=12
BRUECKE="vmbr0"
IP="dhcp"
GATEWAY=""
CTID=""
SPEICHER=""
TROCKENLAUF=0
JA=0

# Mealies Standard-Zugang einer frischen Installation (laut Mealie-Doku v3.30)
MEALIE_BENUTZER="changeme@example.com"
MEALIE_PASSWORT="MyPassword"

# Ab dieser lxc-pve-Version läuft aktuelles Docker in Proxmox-Containern ohne Umweg
LXC_PVE_MINDESTENS="6.0.5-2"

CT_ANGELEGT=0

# ---- Ausgabe ----
# Farben nur, wenn die Ausgabe ein Terminal ist (einmal prüfen – in $(...) wäre es nie wahr)
FARBE_AN=0
if [ -t 1 ]; then FARBE_AN=1; fi
farbe() { if [ "$FARBE_AN" = 1 ]; then printf '\033[%sm' "$1"; fi; }
info() { printf '%s➜%s %s\n' "$(farbe 36)" "$(farbe 0)" "$*"; }
ok() { printf '%s✔%s %s\n' "$(farbe 32)" "$(farbe 0)" "$*"; }
warn() { printf '%s⚠%s %s\n' "$(farbe 33)" "$(farbe 0)" "$*" >&2; }
fehler() { printf '%s✖%s %s\n' "$(farbe 31)" "$(farbe 0)" "$*" >&2; exit 1; }

# ---- Reine Hilfsfunktionen (einzeln testbar, lesen von stdin bzw. Parametern) ----

# Wählt den Speicher für den Container. Eingabe: Ausgabe von `pvesm status`.
# Nimmt aktive, lokale Speicher (keine Netzlaufwerke) mit dem meisten freien Platz.
speicher_waehlen() {
  awk 'NR > 1 && $3 == "active" && $2 !~ /^(nfs|cifs|glusterfs|cephfs|pbs|iscsi|iscsidirect|rbd)$/ {
         if ($6 + 0 > max) { max = $6 + 0; name = $1 }
       } END { if (name != "") print name }'
}

# Wählt den Speicher für Vorlagen. Eingabe: `pvesm status --content vztmpl`. Bevorzugt "local".
vorlagenspeicher_waehlen() {
  awk 'NR > 1 && $3 == "active" { if ($1 == "local") { print $1; found = 1; exit } if (first == "") first = $1 }
       END { if (!found && first != "") print first }'
}

# Wählt die neueste Debian-12-Vorlage. Eingabe: `pveam available --section system`.
vorlage_waehlen() {
  awk '$2 ~ /^debian-12-standard_/ { print $2 }' | sort -V | tail -n 1
}

# Ist Version $1 älter als Version $2? (0 = ja)
version_aelter() {
  [ "$1" != "$2" ] && [ "$(printf '%s\n%s\n' "$1" "$2" | sort -V | head -n 1)" = "$1" ]
}

# Ist $1 "dhcp" oder eine IPv4-Adresse mit Netzmaske, z. B. 192.168.1.50/24?
ip_gueltig() {
  [ "$1" = "dhcp" ] && return 0
  printf '%s' "$1" | grep -Eq '^([0-9]{1,3}\.){3}[0-9]{1,3}/[0-9]{1,2}$'
}

hilfe() {
  cat <<EOF
Rührwerk-Installer ${INSTALLER_VERSION}

Aufruf: ruehrwerk.sh [Optionen]
  --trockenlauf      Nur anzeigen, was passieren würde (verändert nichts)
  --ja               Rückfrage vor dem Anlegen überspringen
  --id NUMMER        Container-Nummer (Standard: nächste freie)
  --name NAME        Container-Name (Standard: ${NAME})
  --speicher NAME    Speicher für den Container (Standard: automatisch)
  --bruecke NAME     Netzwerkbrücke (Standard: ${BRUECKE})
  --ip dhcp|IP/Netz  Adresse, z. B. 192.168.1.50/24 (Standard: dhcp)
  --gateway IP       Gateway (nur bei fester IP nötig)
  --kerne N          CPU-Kerne (Standard: ${KERNE})
  --ram MB           Arbeitsspeicher (Standard: ${RAM})
  --platte GB        Festplatte (Standard: ${PLATTE})
  --quelle URL|DATEI Rührwerk-Quellcode (Tarball-Adresse oder Datei auf diesem Host)
  --hilfe            Diese Hilfe
EOF
}

argumente_lesen() {
  while [ $# -gt 0 ]; do
    case "$1" in
      --trockenlauf) TROCKENLAUF=1 ;;
      --ja) JA=1 ;;
      --id) CTID="${2:?--id braucht eine Nummer}"; shift ;;
      --name) NAME="${2:?--name braucht einen Namen}"; shift ;;
      --speicher) SPEICHER="${2:?--speicher braucht einen Namen}"; shift ;;
      --bruecke) BRUECKE="${2:?--bruecke braucht einen Namen}"; shift ;;
      --ip) IP="${2:?--ip braucht einen Wert}"; shift ;;
      --gateway) GATEWAY="${2:?--gateway braucht eine Adresse}"; shift ;;
      --kerne) KERNE="${2:?--kerne braucht eine Zahl}"; shift ;;
      --ram) RAM="${2:?--ram braucht eine Zahl}"; shift ;;
      --platte) PLATTE="${2:?--platte braucht eine Zahl}"; shift ;;
      --quelle) QUELLE="${2:?--quelle braucht eine Adresse oder Datei}"; shift ;;
      --hilfe | -h | --help) hilfe; exit 0 ;;
      *) fehler "Unbekannte Option: $1 (siehe --hilfe)" ;;
    esac
    shift
  done
  ip_gueltig "$IP" || fehler "Ungültige --ip: $IP (erlaubt: dhcp oder z. B. 192.168.1.50/24)"
  if [ "$IP" != "dhcp" ] && [ -z "$GATEWAY" ]; then fehler "Bei fester IP wird zusätzlich --gateway gebraucht."; fi
  case "$KERNE$RAM$PLATTE" in *[!0-9]*) fehler "--kerne, --ram und --platte müssen Zahlen sein." ;; esac
}

# ---- Ausführen mit Trockenlauf-Unterstützung ----
ausfuehren() {
  if [ "$TROCKENLAUF" = 1 ]; then
    printf '%s[Trockenlauf]%s %s\n' "$(farbe 35)" "$(farbe 0)" "$*"
  else
    "$@"
  fi
}

# Führt ein Skript (von stdin) im Container aus. Titel in $1.
im_container() {
  local titel="$1" datei
  datei="$(mktemp)"
  cat >"$datei"
  if [ "$TROCKENLAUF" = 1 ]; then
    printf '%s[Trockenlauf]%s Im Container %s: %s\n' "$(farbe 35)" "$(farbe 0)" "${CTID:-?}" "$titel"
    rm -f "$datei"
    return 0
  fi
  info "$titel"
  pct push "$CTID" "$datei" /root/schritt.sh --perms 0755
  rm -f "$datei"
  pct exec "$CTID" -- bash /root/schritt.sh
  pct exec "$CTID" -- rm -f /root/schritt.sh
}

bei_fehler() {
  local zeile="$1"
  warn "Abgebrochen in Zeile ${zeile}."
  if [ "$CT_ANGELEGT" = 1 ]; then
    warn "Der neue Container ${CTID} wurde angelegt und NICHT gelöscht. Entfernen mit:"
    warn "  pct stop ${CTID}; pct destroy ${CTID}"
  fi
}
trap 'bei_fehler $LINENO' ERR

# ---- Vorprüfungen ----
vorpruefungen() {
  [ "$(id -u)" = 0 ] || fehler "Bitte als root ausführen (in der Proxmox-Shell)."
  for programm in pct pveam pvesm pvesh pveversion curl; do
    command -v "$programm" >/dev/null 2>&1 || fehler "Dieses Script gehört auf einen Proxmox-VE-Host ('$programm' fehlt)."
  done
  PVE_VERSION="$(pveversion | sed -n 's#^pve-manager/\([0-9][0-9.]*\).*#\1#p')"
  case "$PVE_VERSION" in
    8.*) ok "Proxmox VE ${PVE_VERSION}" ;;
    *) warn "Proxmox VE ${PVE_VERSION:-unbekannt}: nur Version 8.x war vorgesehen. Weiter auf eigene Verantwortung." ;;
  esac
  LXC_PVE="$(dpkg-query -W -f='${Version}' lxc-pve 2>/dev/null || true)"
  if [ -n "$LXC_PVE" ] && version_aelter "$LXC_PVE" "$LXC_PVE_MINDESTENS"; then
    LXC_ALT=1
    warn "lxc-pve ${LXC_PVE} ist älter als ${LXC_PVE_MINDESTENS}: Aktuelles Docker scheitert dort in Containern (AppArmor/runc)."
    warn "Der Installer testet Docker und weicht bei Bedarf auf eine ältere containerd-Version aus."
  else
    LXC_ALT=0
  fi
  ip link show "$BRUECKE" >/dev/null 2>&1 || fehler "Netzwerkbrücke '${BRUECKE}' gibt es nicht. Mit --bruecke angeben (siehe: ip link)."
}

planen() {
  if [ -z "$SPEICHER" ]; then
    SPEICHER="$(pvesm status --content rootdir | speicher_waehlen)"
    [ -n "$SPEICHER" ] || fehler "Kein passender Speicher gefunden. Bitte --speicher angeben (Liste: pvesm status)."
  fi
  pvesm status --content rootdir | awk -v s="$SPEICHER" 'NR > 1 && $1 == s { found = 1 } END { exit !found }' \
    || fehler "Speicher '${SPEICHER}' kann keine Container aufnehmen."
  VORLAGENSPEICHER="$(pvesm status --content vztmpl | vorlagenspeicher_waehlen)"
  [ -n "$VORLAGENSPEICHER" ] || fehler "Kein Speicher für Container-Vorlagen gefunden."
  if [ -z "$CTID" ]; then
    CTID="$(pvesh get /cluster/nextid)"
  else
    pvesh get /cluster/nextid --vmid "$CTID" >/dev/null 2>&1 || fehler "Nummer ${CTID} ist schon vergeben. Bestehende Container werden nie überschrieben."
  fi
  if [ "$IP" = dhcp ]; then NET0="name=eth0,bridge=${BRUECKE},ip=dhcp"; else NET0="name=eth0,bridge=${BRUECKE},ip=${IP},gw=${GATEWAY}"; fi
  ZEITZONE="$(cat /etc/timezone 2>/dev/null || echo Europe/Berlin)"

  cat <<EOF

  Das wird eingerichtet:
    Neuer Container    ${CTID} (${NAME}), Debian 12, ${KERNE} Kerne, ${RAM} MB RAM, ${PLATTE} GB
    Speicher           ${SPEICHER}   (Vorlagen: ${VORLAGENSPEICHER})
    Netzwerk           ${NET0}
    Software           Docker, Mealie ${MEALIE_VERSION}, Rührwerk
    Rührwerk-Quelle    ${QUELLE}
    Zeitzone           ${ZEITZONE}
  Bestehende Container und der Proxmox-Host selbst bleiben unverändert.

EOF
}

bestaetigen() {
  [ "$TROCKENLAUF" = 1 ] && return 0
  [ "$JA" = 1 ] && return 0
  local antwort=""
  read -r -p "Jetzt einrichten? [j/N] " antwort </dev/tty || true
  case "$antwort" in j | J | ja | Ja | JA) ;; *) fehler "Abgebrochen. Es wurde nichts verändert." ;; esac
}

# ---- Schritte ----
vorlage_besorgen() {
  ausfuehren pveam update
  if [ "$TROCKENLAUF" = 1 ]; then
    VORLAGE="$(pveam available --section system 2>/dev/null | vorlage_waehlen || true)"
    VORLAGE="${VORLAGE:-debian-12-standard_…}"
  else
    VORLAGE="$(pveam available --section system | vorlage_waehlen)"
  fi
  [ -n "$VORLAGE" ] || fehler "Keine Debian-12-Vorlage gefunden."
  if pveam list "$VORLAGENSPEICHER" 2>/dev/null | grep -q "$VORLAGE"; then
    ok "Vorlage ${VORLAGE} ist schon vorhanden."
  else
    info "Lade Vorlage ${VORLAGE} herunter …"
    ausfuehren pveam download "$VORLAGENSPEICHER" "$VORLAGE"
  fi
}

container_anlegen() {
  info "Lege Container ${CTID} an …"
  ausfuehren pct create "$CTID" "${VORLAGENSPEICHER}:vztmpl/${VORLAGE}" \
    --hostname "$NAME" --cores "$KERNE" --memory "$RAM" --swap 512 \
    --rootfs "${SPEICHER}:${PLATTE}" --net0 "$NET0" \
    --features nesting=1,keyctl=1 --unprivileged 1 --onboot 1 \
    --tags ruehrwerk --ostype debian
  [ "$TROCKENLAUF" = 1 ] || CT_ANGELEGT=1
  ausfuehren pct start "$CTID"
}

auf_netz_warten() {
  CT_IP="<IP-Adresse>"
  [ "$TROCKENLAUF" = 1 ] && return 0
  info "Warte auf das Netzwerk im Container …"
  local i
  for i in $(seq 1 60); do
    CT_IP="$(pct exec "$CTID" -- hostname -I 2>/dev/null | awk '{print $1}' || true)"
    if [ -n "$CT_IP" ] && pct exec "$CTID" -- getent hosts deb.debian.org >/dev/null 2>&1; then
      ok "Container erreichbar unter ${CT_IP}"
      return 0
    fi
    sleep 2
  done
  fehler "Der Container bekommt kein Netzwerk. Prüfe Brücke, DHCP und DNS."
}

docker_installieren() {
  im_container "Installiere Docker (offizielles Paket-Repository von Docker) …" <<'EOF'
set -Eeuo pipefail
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq ca-certificates curl gnupg jq >/dev/null
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.asc
chmod a+r /etc/apt/keyrings/docker.asc
cat >/etc/apt/sources.list.d/docker.sources <<DOCKER
Types: deb
URIs: https://download.docker.com/linux/debian
Suites: bookworm
Components: stable
Signed-By: /etc/apt/keyrings/docker.asc
DOCKER
apt-get update -qq
apt-get install -y -qq docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin >/dev/null
systemctl enable --now docker >/dev/null 2>&1
echo "Docker installiert: $(docker --version)"
EOF
}

# Startet einen Mini-Container als Test. Schlägt das mit dem bekannten AppArmor-Fehler fehl,
# wird containerd.io auf die neueste Version VOR 1.7.28-2 festgesetzt (laut runc#4968 / Proxmox-Forum).
docker_selbsttest() {
  im_container "Teste, ob Docker in diesem Container läuft …" <<'EOF'
set -Eeuo pipefail
if docker run --rm hello-world >/tmp/dockertest.log 2>&1; then
  echo "Docker-Selbsttest bestanden."
  exit 0
fi
if ! grep -q "ip_unprivileged_port_start" /tmp/dockertest.log; then
  cat /tmp/dockertest.log
  echo "Docker-Selbsttest FEHLGESCHLAGEN (anderer Fehler, siehe oben)." >&2
  exit 1
fi
echo "Bekannter Fehler (AppArmor/runc in altem Proxmox) erkannt. Weiche auf ältere containerd-Version aus …"
ziel=""
for v in $(apt-cache madison containerd.io | awk '{print $3}'); do
  if dpkg --compare-versions "$v" lt "1.7.28-2~~"; then ziel="$v"; break; fi
done
[ -n "$ziel" ] || { echo "Keine passende ältere containerd-Version gefunden. Bitte Proxmox aktualisieren (apt dist-upgrade)." >&2; exit 1; }
apt-get install -y -qq --allow-downgrades "containerd.io=$ziel" >/dev/null
apt-mark hold containerd.io >/dev/null
systemctl restart docker
if docker run --rm hello-world >/tmp/dockertest.log 2>&1; then
  echo "Docker-Selbsttest bestanden mit containerd.io ${ziel} (festgesetzt)."
else
  cat /tmp/dockertest.log
  echo "Auch mit älterem containerd schlägt Docker fehl. Bitte Proxmox aktualisieren (apt dist-upgrade) und neu starten." >&2
  exit 1
fi
EOF
}

quellcode_holen() {
  if [ -f "$QUELLE" ]; then
    info "Verwende lokale Quelldatei ${QUELLE}"
    ausfuehren pct push "$CTID" "$QUELLE" /root/ruehrwerk-quelle.tar.gz
    QUELLE_BEFEHL="tar -xz --strip-components=1 -C /opt/ruehrwerk/quelle -f /root/ruehrwerk-quelle.tar.gz"
  else
    QUELLE_BEFEHL="curl -fsSL '${QUELLE}' | tar -xz --strip-components=1 -C /opt/ruehrwerk/quelle"
  fi
  im_container "Hole den Rührwerk-Quellcode …" <<EOF
set -Eeuo pipefail
mkdir -p /opt/ruehrwerk/quelle
${QUELLE_BEFEHL}
test -f /opt/ruehrwerk/quelle/Dockerfile || { echo "Im Quellcode fehlt das Dockerfile." >&2; exit 1; }
EOF
}

dienste_einrichten() {
  # Unquotiertes Heredoc: ${…} wird HIER (auf dem Host) eingesetzt.
  im_container "Richte Mealie und Rührwerk ein und starte Mealie …" <<EOF
set -Eeuo pipefail
cd /opt/ruehrwerk
cat >docker-compose.yml <<COMPOSE
services:
  mealie:
    image: ghcr.io/mealie-recipes/mealie:${MEALIE_VERSION}
    container_name: mealie
    restart: unless-stopped
    ports:
      - "9000:9000"
    deploy:
      resources:
        limits:
          memory: 1000M
    volumes:
      - mealie-daten:/app/data/
    environment:
      ALLOW_SIGNUP: "false"
      PUID: 1000
      PGID: 1000
      TZ: ${ZEITZONE}
      BASE_URL: http://${CT_IP}:9000
  ruehrwerk:
    build: ./quelle
    container_name: ruehrwerk
    restart: unless-stopped
    ports:
      - "8080:8080"
    env_file: .env
    volumes:
      - ruehrwerk-daten:/data
    depends_on:
      - mealie
volumes:
  mealie-daten:
  ruehrwerk-daten:
COMPOSE
umask 077
printf 'MEALIE_URL=http://mealie:9000\nMEALIE_TOKEN=\n' >.env
docker compose up -d mealie
EOF
}

token_erzeugen() {
  im_container "Warte auf Mealie, erzeuge den API-Token und starte Rührwerk …" <<EOF
set -Eeuo pipefail
cd /opt/ruehrwerk
echo "Warte, bis Mealie bereit ist (das dauert beim ersten Start etwas) …"
bereit=0
for i in \$(seq 1 120); do
  if curl -fsS http://localhost:9000/api/app/about >/dev/null 2>&1; then bereit=1; break; fi
  sleep 3
done
[ "\$bereit" = 1 ] || { echo "Mealie wurde nicht rechtzeitig bereit. Logs: docker logs mealie" >&2; exit 1; }
zugang="\$(curl -fsS -X POST http://localhost:9000/api/auth/token -d 'username=${MEALIE_BENUTZER}' -d 'password=${MEALIE_PASSWORT}' | jq -r .access_token)"
[ -n "\$zugang" ] && [ "\$zugang" != null ] || { echo "Anmeldung bei Mealie fehlgeschlagen." >&2; exit 1; }
token="\$(curl -fsS -X POST http://localhost:9000/api/users/api-tokens -H "Authorization: Bearer \$zugang" -H 'Content-Type: application/json' -d '{"name":"ruehrwerk"}' | jq -r .token)"
[ -n "\$token" ] && [ "\$token" != null ] || { echo "Konnte keinen API-Token erzeugen." >&2; exit 1; }
umask 077
printf 'MEALIE_URL=http://mealie:9000\nMEALIE_TOKEN=%s\n' "\$token" >.env
echo "API-Token erzeugt und bei Rührwerk eingetragen."
docker compose up -d --build ruehrwerk
EOF
}

pruefen_und_abschluss() {
  if [ "$TROCKENLAUF" = 1 ]; then
    cat <<EOF

$(farbe 35)Trockenlauf beendet – es wurde nichts verändert.$(farbe 0)
Zum echten Einrichten denselben Befehl ohne "_ --trockenlauf" ausführen.
EOF
    return 0
  fi
  info "Prüfe, ob Rührwerk Mealie erreicht …"
  local i antwort=""
  for i in $(seq 1 30); do
    antwort="$(pct exec "$CTID" -- curl -fsS -X POST http://localhost:8080/api/verbindung-testen 2>/dev/null || true)"
    case "$antwort" in *version*) break ;; esac
    sleep 3
  done
  case "$antwort" in
    *version*) ok "Rührwerk ist mit Mealie verbunden." ;;
    *) warn "Rührwerk läuft, aber die Verbindungsprüfung hat nicht geklappt. Logs: pct exec ${CTID} -- docker logs ruehrwerk" ;;
  esac
  cat <<EOF

$(farbe 32)Fertig!$(farbe 0)

  Rührwerk (zum Kochen):   http://${CT_IP}:8080
  Mealie (Rezeptverwaltung): http://${CT_IP}:9000

  $(farbe 33)WICHTIG – Standard-Zugang von Mealie:$(farbe 0)
    Benutzer:  ${MEALIE_BENUTZER}
    Passwort:  ${MEALIE_PASSWORT}
  Dieses Passwort ist öffentlich bekannt. Ändere es gleich in Mealie
  (oben rechts: Benutzerprofil → Passwort ändern) und trage deine eigene E-Mail ein.
  Betreibe beides nur im Heimnetz, nicht offen im Internet.

  Hinweis: Auf dem Handy funktionieren Bildschirm-wach-halten und Offline-Betrieb nur über HTTPS.
  Zum Ausprobieren reicht http://.

  Container ${CTID} in der Konsole öffnen:   pct enter ${CTID}
  Wieder entfernen (löscht alle Daten!):     pct stop ${CTID}; pct destroy ${CTID}
EOF
  if [ "${LXC_ALT:-0}" = 1 ]; then
    warn "Dein Proxmox (lxc-pve ${LXC_PVE}) ist älter als ${LXC_PVE_MINDESTENS}. Falls der Installer containerd.io festgesetzt hat,"
    warn "aktualisiere Proxmox bei Gelegenheit (apt update && apt dist-upgrade) und gib es dann im Container frei: apt-mark unhold containerd.io"
  fi
}

main() {
  argumente_lesen "$@"
  printf '%sRührwerk-Installer %s%s%s\n' "$(farbe 1)" "$INSTALLER_VERSION" "$([ "$TROCKENLAUF" = 1 ] && printf ' (Trockenlauf)')" "$(farbe 0)"
  vorpruefungen
  planen
  bestaetigen
  vorlage_besorgen
  container_anlegen
  auf_netz_warten
  docker_installieren
  docker_selbsttest
  quellcode_holen
  dienste_einrichten
  token_erzeugen
  pruefen_und_abschluss
}

# Beim Testen mit RUEHRWERK_NO_MAIN=1 nur die Funktionen laden
if [ -z "${RUEHRWERK_NO_MAIN:-}" ]; then
  main "$@"
fi

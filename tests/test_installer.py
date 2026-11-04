"""Tests für den Proxmox-Installer (install/ruehrwerk.sh).

Die Logik-Funktionen werden direkt geprüft; zusätzlich läuft ein kompletter Trockenlauf mit
nachgestellten Proxmox-Befehlen (pct, pvesm, ...). Die Beispieldaten stammen aus dem echten
`pvesm status` des Zielsystems (Proxmox 8.2.2, Kernel 6.8.4-2-pve).
"""

import os
import stat
import subprocess
from pathlib import Path

import pytest

SKRIPT = Path(__file__).resolve().parent.parent / "install" / "ruehrwerk.sh"

PVESM_ALLE = """\
Name                Type     Status           Total            Used       Available        %
local                dir     active        98497780        72848764        20599468   73.96%
local-lvm        lvmthin     active       365760512       180795421       184965090   49.43%
ugreen_backup        nfs     active      7735265280      7149775872       585473024   92.43%
"""

PVEAM_VERFUEGBAR = """\
system          debian-11-standard_11.7-1_amd64.tar.zst
system          debian-12-standard_12.2-1_amd64.tar.zst
system          debian-12-standard_12.7-1_amd64.tar.zst
system          debian-13-standard_13.0-1_amd64.tar.zst
system          ubuntu-24.04-standard_24.04-2_amd64.tar.zst
"""


def lauf(code: str, eingabe: str = "", env=None) -> subprocess.CompletedProcess:
    """Lädt nur die Funktionen des Scripts und führt `code` aus."""
    umgebung = {**os.environ, "RUEHRWERK_NO_MAIN": "1", **(env or {})}
    return subprocess.run(
        ["bash", "-c", f'source "{SKRIPT}"; {code}'], input=eingabe, capture_output=True, text=True, env=umgebung
    )


def test_syntax_ist_gueltig():
    assert subprocess.run(["bash", "-n", str(SKRIPT)]).returncode == 0


def test_speicher_waehlt_lvm_thin_aus_dem_echten_system():
    # local hat nur ~20 GB frei, ugreen_backup ist ein NFS-Netzlaufwerk -> local-lvm
    assert lauf("speicher_waehlen", PVESM_ALLE).stdout.strip() == "local-lvm"


def test_speicher_ignoriert_netzlaufwerke_und_inaktive():
    nur_nfs = "Name Type Status Total Used Available %\nnas nfs active 100 1 99 1%\nweg dir inactive 100 1 99 1%\n"
    assert lauf("speicher_waehlen", nur_nfs).stdout.strip() == ""


def test_vorlagenspeicher_bevorzugt_local():
    eingabe = "Name Type Status Total Used Available %\nandere dir active 1 1 1 1%\nlocal dir active 1 1 1 1%\n"
    assert lauf("vorlagenspeicher_waehlen", eingabe).stdout.strip() == "local"
    eingabe2 = "Name Type Status Total Used Available %\nandere dir active 1 1 1 1%\n"
    assert lauf("vorlagenspeicher_waehlen", eingabe2).stdout.strip() == "andere"


def test_vorlage_ist_neueste_debian_12():
    assert lauf("vorlage_waehlen", PVEAM_VERFUEGBAR).stdout.strip() == "debian-12-standard_12.7-1_amd64.tar.zst"


@pytest.mark.parametrize(
    "alt,neu,erwartet",
    [("6.0.0-1", "6.0.5-2", 0), ("6.0.5-1", "6.0.5-2", 0), ("6.0.5-2", "6.0.5-2", 1), ("6.0.6-1", "6.0.5-2", 1), ("5.9.9-9", "6.0.5-2", 0)],
)
def test_version_aelter(alt, neu, erwartet):
    assert lauf(f'version_aelter "{alt}" "{neu}"').returncode == erwartet


@pytest.mark.parametrize(
    "wert,gueltig",
    [("dhcp", True), ("192.168.1.50/24", True), ("10.0.0.2/8", True), ("192.168.1.50", False), ("hallo", False), ("1.2.3/24", False), ("", False)],
)
def test_ip_gueltig(wert, gueltig):
    assert (lauf(f'ip_gueltig "{wert}"').returncode == 0) is gueltig


def test_feste_ip_braucht_gateway():
    r = lauf('argumente_lesen --ip 192.168.1.50/24')
    assert r.returncode != 0 and "gateway" in r.stderr.lower()


def test_unbekannte_option_wird_abgelehnt():
    r = lauf("argumente_lesen --unsinn")
    assert r.returncode != 0 and "Unbekannte Option" in r.stderr


def test_zahlen_werden_geprueft():
    assert lauf("argumente_lesen --ram viel").returncode != 0


# ---- Kompletter Trockenlauf mit nachgestellten Proxmox-Befehlen ----
def _stub(ordner: Path, name: str, inhalt: str):
    datei = ordner / name
    datei.write_text("#!/bin/sh\n" + inhalt)
    datei.chmod(datei.stat().st_mode | stat.S_IEXEC)


@pytest.fixture
def proxmox_attrappe(tmp_path):
    ordner = tmp_path / "bin"
    ordner.mkdir()
    protokoll = tmp_path / "aufrufe.log"
    # Beispieldaten liegen in Dateien, die Attrappen geben sie nur aus.
    (tmp_path / "pvesm_rootdir.txt").write_text(PVESM_ALLE)
    (tmp_path / "pvesm_vztmpl.txt").write_text(
        "Name Type Status Total Used Available %\nlocal dir active 98497780 72848764 20599468 73.96%\n"
    )
    (tmp_path / "pveam_available.txt").write_text(PVEAM_VERFUEGBAR)
    # Alles, was etwas verändern würde, wird protokolliert – im Trockenlauf darf das Protokoll leer bleiben.
    _stub(ordner, "pct", f'echo "pct $*" >> "{protokoll}"\n')
    _stub(ordner, "id", "echo 0\n")
    _stub(ordner, "ip", "exit 0\n")
    _stub(ordner, "pveversion", 'echo "pve-manager/8.2.2/9355359cd7afc301 (running kernel: 6.8.4-2-pve)"\n')
    _stub(ordner, "dpkg-query", "echo 6.0.0-1\n")
    _stub(ordner, "pvesh", f'echo "pvesh $*" >> "{protokoll}"\necho 105\n')
    _stub(
        ordner,
        "pvesm",
        f'case "$*" in\n  *vztmpl*) cat "{tmp_path}/pvesm_vztmpl.txt";;\n  *) cat "{tmp_path}/pvesm_rootdir.txt";;\nesac\n',
    )
    _stub(
        ordner,
        "pveam",
        f'case "$1" in\n  available) cat "{tmp_path}/pveam_available.txt";;\n'
        f'  list) echo "Name Size";;\n  *) echo "pveam $*" >> "{protokoll}";;\nesac\n',
    )
    return ordner, protokoll


def test_trockenlauf_aendert_nichts(proxmox_attrappe):
    ordner, protokoll = proxmox_attrappe
    env = {**os.environ, "PATH": f"{ordner}:{os.environ['PATH']}"}
    r = subprocess.run(["bash", str(SKRIPT), "--trockenlauf"], capture_output=True, text=True, env=env)
    ausgabe = r.stdout + r.stderr
    assert r.returncode == 0, ausgabe
    # Plan nennt Speicher, Nummer und Software
    assert "Neuer Container    105" in ausgabe and "local-lvm" in ausgabe and "Mealie v3.30.0" in ausgabe
    # Warnung wegen altem lxc-pve
    assert "lxc-pve 6.0.0-1" in ausgabe
    # Alle verändernden Schritte nur angekündigt
    assert "[Trockenlauf] pct create 105 local:vztmpl/debian-12-standard_12.7-1_amd64.tar.zst" in ausgabe
    assert "--features nesting=1,keyctl=1 --unprivileged 1" in ausgabe
    assert "--rootfs local-lvm:12" in ausgabe
    assert "Trockenlauf beendet" in ausgabe
    # Es wurde wirklich kein pct aufgerufen und keine Nummer verändert (nur nextid gelesen)
    aufrufe = protokoll.read_text() if protokoll.exists() else ""
    assert "pct" not in aufrufe
    assert "pveam update" not in aufrufe and "pveam download" not in aufrufe


def test_vergebene_nummer_wird_abgelehnt(proxmox_attrappe):
    ordner, _ = proxmox_attrappe
    _stub(ordner, "pvesh", 'case "$*" in *--vmid*) exit 1;; esac\necho 105\n')
    env = {**os.environ, "PATH": f"{ordner}:{os.environ['PATH']}"}
    r = subprocess.run(["bash", str(SKRIPT), "--trockenlauf", "--id", "100"], capture_output=True, text=True, env=env)
    assert r.returncode != 0 and "schon vergeben" in r.stderr


def test_nicht_root_wird_abgelehnt(proxmox_attrappe):
    ordner, _ = proxmox_attrappe
    _stub(ordner, "id", 'echo 1000\n')
    env = {**os.environ, "PATH": f"{ordner}:{os.environ['PATH']}"}
    r = subprocess.run(["bash", str(SKRIPT), "--trockenlauf"], capture_output=True, text=True, env=env)
    assert r.returncode != 0 and "root" in r.stderr


# ---- Die im Container laufenden Skripte: Syntax und erzeugte Compose-Datei ----
def _erzeugte_skripte(tmp_path: Path) -> dict[str, str]:
    """Lässt den Installer seine Container-Skripte erzeugen, ohne etwas auszuführen."""
    ausgabe = tmp_path / "skripte"
    ausgabe.mkdir()
    code = f"""
    im_container() {{ cat > "{ausgabe}/$(printf '%s' "$1" | tr -c 'a-zA-Z' '_' | cut -c1-30).sh"; }}
    ZEITZONE=Europe/Berlin; CT_IP=192.168.1.77; CTID=105; QUELLE=https://example.org/x.tar.gz
    docker_installieren; docker_selbsttest; quellcode_holen; dienste_einrichten; token_erzeugen
    """
    r = lauf(code)
    assert r.returncode == 0, r.stderr
    return {p.name: p.read_text() for p in ausgabe.iterdir()}


def test_container_skripte_haben_gueltige_syntax(tmp_path):
    skripte = _erzeugte_skripte(tmp_path)
    assert len(skripte) == 5
    for name, text in skripte.items():
        pruefung = subprocess.run(["bash", "-n"], input=text, capture_output=True, text=True)
        assert pruefung.returncode == 0, f"{name}: {pruefung.stderr}"


def test_erzeugte_compose_datei_ist_gueltiges_yaml(tmp_path):
    import yaml

    skripte = _erzeugte_skripte(tmp_path)
    einrichten = next(t for n, t in skripte.items() if n.startswith("Richte"))
    compose = einrichten.split("<<COMPOSE\n", 1)[1].split("\nCOMPOSE\n", 1)[0]
    daten = yaml.safe_load(compose)
    mealie, rw = daten["services"]["mealie"], daten["services"]["ruehrwerk"]
    assert mealie["image"] == "ghcr.io/mealie-recipes/mealie:v3.30.0"
    assert mealie["environment"]["BASE_URL"] == "http://192.168.1.77:9000"
    assert mealie["environment"]["ALLOW_SIGNUP"] == "false" and mealie["environment"]["TZ"] == "Europe/Berlin"
    assert rw["build"] == "./quelle" and rw["env_file"] == ".env" and rw["depends_on"] == ["mealie"]
    assert set(daten["volumes"]) == {"mealie-daten", "ruehrwerk-daten"}


def test_token_skript_haelt_variablen_fuer_den_container_zurueck(tmp_path):
    skripte = _erzeugte_skripte(tmp_path)
    text = next(t for n, t in skripte.items() if n.startswith("Warte"))
    # Diese Variablen müssen im Container-Skript noch als $name stehen (nicht schon auf dem Host eingesetzt)
    for stueck in ('"$zugang"', '"$token"', "Authorization: Bearer $zugang", "MEALIE_TOKEN=%s"):
        assert stueck in text, stueck
    assert "username=changeme@example.com" in text and "/api/users/api-tokens" in text
    assert "MyPassword" in text  # Standard-Zugang laut Mealie-Doku
    assert "docker compose up -d --build ruehrwerk" in text

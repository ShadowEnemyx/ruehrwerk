"""Erzeugt die App-Symbole (PNG) ohne Zusatzpakete: grüner Grund, weißer Topfrand, dreiflügeliges Rührwerk.

Aufruf:  python3 tools/icons.py
"""

import math
import struct
import zlib
from pathlib import Path

GRUND = (47, 111, 79)
VORDERGRUND = (250, 247, 242)


def abstand_zur_strecke(px, py, ax, ay, bx, by):
    dx, dy = bx - ax, by - ay
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def ist_vordergrund(x, y, n, skala):
    """x, y in 0..1. skala < 1 schrumpft das Motiv (für maskierbare Symbole)."""
    mx = my = 0.5
    px, py = (x - mx) / skala + mx, (y - my) / skala + my
    d = math.hypot(px - mx, py - my)
    if abs(d - 0.30) < 0.0225:  # Topfrand
        return True
    if d < 0.045:  # Nabe
        return True
    for i in range(3):  # drei Flügel
        w = math.radians(90 + i * 120)
        ex, ey = mx + 0.24 * math.cos(w), my - 0.24 * math.sin(w)
        if abstand_zur_strecke(px, py, mx, my, ex, ey) < 0.03:
            return True
    return False


def png(n, skala, ziel: Path):
    zeilen = bytearray()
    ss = 3  # Überabtastung für glatte Kanten
    for j in range(n):
        zeilen.append(0)
        for i in range(n):
            treffer = sum(
                ist_vordergrund((i + (a + 0.5) / ss) / n, (j + (b + 0.5) / ss) / n, n, skala)
                for a in range(ss)
                for b in range(ss)
            )
            f = treffer / (ss * ss)
            zeilen.extend(round(g + (v - g) * f) for g, v in zip(GRUND, VORDERGRUND))
    def chunk(typ, daten):
        c = struct.pack(">I", len(daten)) + typ + daten
        return c + struct.pack(">I", zlib.crc32(typ + daten))
    kopf = struct.pack(">IIBBBBB", n, n, 8, 2, 0, 0, 0)
    ziel.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", kopf) + chunk(b"IDAT", zlib.compress(bytes(zeilen), 9)) + chunk(b"IEND", b""))


if __name__ == "__main__":
    ordner = Path(__file__).resolve().parent.parent / "web" / "icons"
    ordner.mkdir(parents=True, exist_ok=True)
    png(180, 1.0, ordner / "apple-touch-icon.png")
    png(192, 1.0, ordner / "icon-192.png")
    png(512, 1.0, ordner / "icon-512.png")
    png(512, 0.8, ordner / "icon-maskable-512.png")  # Motiv in der sicheren Zone
    print("Symbole erzeugt in", ordner)

"""Kleiner Ersatz für Mealie – NUR zum Ausprobieren der Oberfläche ohne Docker.

Bildet die in Mealie v3.30.0 geprüften Endpunkte und das camelCase-Schema nach, mit selbst erfundenen Rezepten.
Der Test gegen eine echte Mealie ersetzt das nicht.

Start:  .venv/bin/python -m uvicorn tools.fake_mealie:app --port 9000
"""

import base64

from fastapi import FastAPI, HTTPException, Response

app = FastAPI()

PNG = base64.b64decode(  # 1x1 grünes Pixel
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
)


def zutat(ref, menge, einheit, name, notiz="", display=None):
    return {
        "referenceId": ref, "quantity": menge, "title": None,
        "unit": {"name": einheit, "abbreviation": einheit, "useAbbreviation": True} if einheit else None,
        "food": {"name": name}, "note": notiz,
        "display": display or f"{menge} {einheit or ''} {name} {notiz}".replace("  ", " ").strip(),
    }


REZEPTE = {
    "kuerbissuppe": {
        "id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa", "slug": "kuerbissuppe", "name": "Kürbissuppe (Test)",
        "description": "Selbst erfundenes Testrezept.", "image": "x", "recipeServings": 4, "recipeYieldQuantity": 0,
        "recipeIngredient": [
            zutat("z1", 500, "g", "Hokkaido-Kürbis", "in Stücken"),
            zutat("z2", 1, "", "Zwiebel", "halbiert"),
            zutat("z3", 600, "ml", "Gemüsebrühe"),
            {"referenceId": "z4", "quantity": 0, "unit": None, "food": None, "display": "", "originalText": "Salz und Pfeffer nach Geschmack"},
        ],
        "recipeInstructions": [
            {"id": "s1", "title": "Vorbereiten", "text": "🧅 Zwiebel in den Mixtopf geben und 5 Sek./Stufe 5 zerkleinern.", "ingredientReferences": [{"referenceId": "z2"}]},
            {"id": "s2", "title": "", "text": "Kürbis und Brühe zugeben, 20 Min./100 °C/Stufe 1 garen.", "ingredientReferences": [{"referenceId": "z1"}, {"referenceId": "z3"}]},
            {"id": "s3", "title": "Pürieren", "text": "1 Min./Stufe 4-5 pürieren, danach 5 Min./100 °C kochen."},
            {"id": "s4", "title": "", "text": "Sanft rühren: 3 Min./80 °C/Linkslauf/Stufe 8 erwärmen."},
            {"id": "s5", "title": "", "text": "Backofen auf 180 °C vorheizen, Brot 10 Min. aufbacken und mit der Suppe servieren."},
        ],
    },
    "leer": {"id": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb", "slug": "leer", "name": "Rezept ohne Schritte", "recipeIngredient": [], "recipeInstructions": []},
}


@app.get("/api/app/about")
def about():
    return {"version": "v3.30.0-fake", "production": False}


@app.get("/api/users/self")
def selbst():
    return {"id": "u"}


@app.get("/api/recipes")
def liste(search: str = "", page: int = 1, perPage: int = 30, orderBy: str = "", orderDirection: str = ""):
    items = [r for r in REZEPTE.values() if search.lower() in r["name"].lower()]
    return {"page": page, "per_page": perPage, "total": len(items), "total_pages": 1, "items": items}


@app.get("/api/recipes/{slug}")
def rezept(slug: str):
    if slug not in REZEPTE:
        raise HTTPException(404)
    return REZEPTE[slug]


@app.post("/api/recipes/create/url", status_code=201)
def importieren(daten: dict):
    if "kaputt" in daten.get("url", ""):
        raise HTTPException(400, {"message": "Konnte nicht gelesen werden"})
    return "kuerbissuppe"


@app.get("/api/media/recipes/{rid}/images/{datei}")
def bild(rid: str, datei: str):
    return Response(PNG, media_type="image/png")

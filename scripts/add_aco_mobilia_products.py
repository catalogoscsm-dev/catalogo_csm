"""Adiciona os 39 produtos da Aço Mobilia 2025-7 ao products.json do site estático.

IDs 1000+ para não colidir com os produtos ABV. Idempotente: remove entradas
Aço Mobilia existentes antes de inserir.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JSON_PATH = ROOT / "products.json"
IMG_DIR = "data/products/Aco Mobilia 2025-7"

# (nome, categoria, [imagens], pag)
PRODUTOS = [
    ("Mesa Athenas", "Mesa", ["pag003_main.jpg", "pag004_tech.jpg"], 3),
    ("Cadeira Athenas", "Cadeira", ["pag003_main.jpg", "pag004_tech.jpg"], 3),
    ("Mesa Santorini", "Mesa", ["pag005_main.jpg", "pag006_tech.jpg"], 5),
    ("Cadeira Santorini", "Cadeira", ["pag005_main.jpg", "pag006_tech.jpg"], 5),
    ("Mesa Santorini com Aplique", "Mesa", ["pag007_main.jpg", "pag008_tech.jpg"], 7),
    ("Mesa Capri", "Mesa", ["pag009_main.jpg", "pag010_tech.jpg"], 9),
    ("Cadeira Atrani", "Cadeira", ["pag009_main.jpg", "pag010_tech.jpg"], 9),
    ("Mesa Sierra", "Mesa", ["pag011_main.jpg", "pag012_tech.png"], 11),
    ("Mesa Louvre", "Mesa", ["pag013_main.jpg", "pag014_tech.jpg"], 13),
    ("Poltrona Luxor", "Poltrona", ["pag013_main.jpg", "pag014_tech.jpg"], 13),
    ("Mesa Milão", "Mesa", ["pag015_main.jpg", "pag016_tech.jpg"], 15),
    ("Cadeira Ágatha", "Cadeira", ["pag015_main.jpg", "pag016_tech.jpg"], 15),
    ("Mesa Amalfi", "Mesa", ["pag017_main.jpg", "pag018_tech.png"], 17),
    ("Poltrona Madrid", "Poltrona", ["pag017_main.jpg", "pag018_tech.png"], 17),
    ("Cadeira Milão", "Cadeira", ["pag019_main.jpg", "pag020_tech.jpg"], 19),
    ("Cadeira Belegio", "Cadeira", ["pag021_main.jpg", "pag022_tech.jpg"], 21),
    ("Cadeira Caribe", "Cadeira", ["pag023_main.jpg", "pag024_tech.jpg"], 23),
    ("Mesa Tapazio", "Mesa", ["pag025_main.jpg", "pag026_tech.jpg"], 25),
    ("Cadeira Madrid", "Cadeira", ["pag029_main.jpg", "pag030_tech.jpg"], 29),
    ("Mesa Madrid", "Mesa", ["pag031_main.jpg", "pag032_tech.jpg"], 31),
    ("Mesa Milão Office", "Mesa", ["pag041_main.jpg", "pag040_tech.jpg"], 41),
    ("Mesa Moorea", "Mesa", ["pag043_main.jpg", "pag042_tech.jpg"], 43),
    ("Cadeira Bora Bora", "Cadeira", ["pag043_main.jpg", "pag044_tech.jpg"], 43),
    ("Mesa Taiti", "Mesa", ["pag045_main.jpg", "pag044_tech.jpg"], 45),
    ("Banqueta Athenas", "Banqueta", ["pag047_main.jpg", "pag046_tech.jpg"], 47),
    ("Bistrô Capri", "Bistrô", ["pag049_main.jpg", "pag048_tech.jpg"], 49),
    ("Banqueta Caribe", "Banqueta", ["pag049_main.jpg", "pag048_tech.jpg"], 49),
    ("Bistrô Maupiti", "Bistrô", ["pag051_main.jpg", "pag050_tech.jpg"], 51),
    ("Banqueta Belegio", "Banqueta", ["pag051_main.jpg", "pag050_tech.jpg"], 51),
    ("Poltrona Polinesia", "Poltrona", ["pag053_main.jpg", "pag054_tech.jpg"], 53),
    ("Mesa Canto Araxa", "Mesa Lateral", ["pag053_main.jpg", "pag054_tech.jpg"], 53),
    ("Mesa Centro Raielas", "Mesa Lateral", ["pag053_main.jpg", "pag054_tech.jpg"], 53),
    ("Mesa Centro Oxturi", "Mesa Lateral", ["pag055_main.jpg", "pag055_tech.jpg"], 55),
    ("Mesa de Centro Atlas", "Mesa Lateral", ["pag056_main.png", "pag056_tech.png"], 56),
    ("Mesa Canto Athenas", "Mesa Lateral", ["pag057_main.png"], 57),
    ("Mesa Canto Sicilia", "Mesa Lateral", ["pag057_main.png"], 57),
    ("Aparador Athenas", "Aparador", ["pag058_main.jpg"], 58),
    ("Aparador Milão", "Aparador", ["pag059_main.jpg"], 59),
    ("Aparador Louvre", "Aparador", ["pag060_main.jpg"], 60),
]

data = json.loads(JSON_PATH.read_text(encoding="utf-8"))
data["produtos"] = [p for p in data["produtos"] if p["fornecedor"] != "Aço Mobilia"]

novos = []
for i, (nome, categoria, imgs, pag) in enumerate(PRODUTOS):
    caminhos = [f"{IMG_DIR}/{f}" for f in imgs]
    for c in caminhos:
        assert (ROOT / c).exists(), f"Imagem em falta: {c}"
    novos.append({
        "id": 1000 + i,
        "nome": nome,
        "categoria": categoria,
        "dimensoes": "",
        "cores": [],
        "imagens": caminhos,
        "fornecedor": "Aço Mobilia",
        "pag": pag,
    })

data["produtos"].extend(novos)
JSON_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"{len(novos)} produtos Aço Mobilia adicionados. Total agora: {len(data['produtos'])}")

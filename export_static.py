"""
Gera products.json a partir do SQLite para o site estático GitHub Pages.
Execute sempre que adicionar novos produtos.
"""
import sqlite3, json, sys
from pathlib import Path
sys.path.insert(0, "webapp")
from config import DB_PATH

conn = sqlite3.connect(str(DB_PATH))
rows = conn.execute(
    "SELECT id, nome, categoria, dimensoes, cores, imagens, fornecedor, pagina_origem "
    "FROM products WHERE aprovado=1 ORDER BY categoria, nome"
).fetchall()

products = []
for r in rows:
    images = json.loads(r[5]) if r[5] else []
    cores  = json.loads(r[4]) if r[4] else []
    products.append({
        "id":         r[0],
        "nome":       r[1],
        "categoria":  r[2],
        "dimensoes":  r[3],
        "cores":      cores,
        "imagens":    images,
        "fornecedor": r[6],
        "pag":        r[7],
    })

conn.close()

out = Path("products.json")
out.write_text(json.dumps({"produtos": products}, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"Exportados {len(products)} produtos -> {out}")

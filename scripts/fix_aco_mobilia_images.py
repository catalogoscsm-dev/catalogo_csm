"""
Extrai as imagens reais do PDF da Aço Mobilia e atualiza o banco.
- Imagem 1 (principal): JPEG embutido de alta qualidade da página ambiente
- Imagem 2 (técnica): renderização da página de especificações
"""
import pymupdf as fitz
import sqlite3
import json
from pathlib import Path

PDF_PATH  = r"C:\Users\joao.miguel\Documents\catalogos\catalogos 3\Aço Mobilia 2025-7.pdf"
DB_PATH   = r"C:\Users\joao.miguel\Documents\csm-catalog-extractor\data\catalog.db"
DATA_DIR  = Path(r"C:\Users\joao.miguel\Documents\csm-catalog-extractor\data")
OUT_DIR   = DATA_DIR / "products" / "Aco Mobilia 2025-7"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Mapeamento pagina_origem → (pag_img1, pag_img2 ou None)
PAGE_PAIRS = {
    3:  (3,  4),    # Mesa Athenas / Cadeira Athenas
    5:  (5,  6),    # Mesa Santorini / Cadeira Santorini
    7:  (7,  8),    # Mesa Santorini com Aplique
    9:  (9,  10),   # Mesa Capri / Cadeira Atrani
    11: (11, 12),   # Mesa Sierra
    13: (13, 14),   # Mesa Louvre / Poltrona Luxor
    15: (15, 16),   # Mesa Milão / Cadeira Ágatha
    17: (17, 18),   # Mesa Amalfi / Poltrona Madrid
    19: (19, 20),   # Cadeira Milão
    21: (21, 22),   # Cadeira Belegio
    23: (23, 24),   # Cadeira Caribe
    25: (25, 26),   # Mesa Tapazio
    29: (29, 30),   # Cadeira Madrid
    31: (31, 32),   # Mesa Madrid
    41: (41, 40),   # Mesa Milão Office  (ambiente=41, técnica=40)
    43: (43, 42),   # Mesa Moorea        (ambiente=43, técnica=42)
    45: (45, 44),   # Mesa Taiti         (ambiente=45, técnica=44)
    47: (47, 46),   # Banqueta Athenas   (ambiente=47, técnica=46)
    49: (49, 48),   # Bistrô Capri / Banqueta Caribe
    51: (51, 50),   # Bistrô Maupiti / Banqueta Belegio
    53: (53, 54),   # Poltrona Polinesia / Mesa Canto Araxa / Mesa Centro Raielas
    55: (55, 56),   # Mesa Centro Oxturi  (56 = Mesa Atlas, boa como complemento)
    56: (56, 55),   # Mesa de Centro Atlas
    57: (57, None), # Mesa Canto Athenas / Mesa Canto Sicilia  (página única)
    58: (58, None), # Aparador Athenas
    59: (59, None), # Aparador Milão
    60: (60, None), # Aparador Louvre
}

# Produtos com par de páginas diferente do padrão da sua pagina_origem
PRODUCT_OVERRIDES = {
    183: (43, 44),  # Cadeira Bora Bora — ambiente=43, técnica=44
}


def extract_best_jpeg(pdf, page_num):
    """Devolve o maior JPEG embutido na página (>= 400x300 px), ou None."""
    page = pdf[page_num - 1]
    best, best_area = None, 0
    seen = set()
    for img in page.get_images(full=True):
        xref = img[0]
        if xref in seen:
            continue
        seen.add(xref)
        info = pdf.extract_image(xref)
        w, h = info["width"], info["height"]
        area = w * h
        if area > best_area and w >= 400 and h >= 300:
            best_area = area
            best = info
    return best


def render_page(pdf, page_num, dpi=150):
    """Renderiza a página e devolve bytes PNG."""
    page = pdf[page_num - 1]
    zoom = dpi / 72
    mat = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=mat, alpha=False)
    return pix.tobytes("png")


def save_page_image(pdf, page_num, stem):
    """Salva a melhor imagem da página; devolve Path relativo ao DATA_DIR."""
    info = extract_best_jpeg(pdf, page_num)
    if info:
        ext = "jpg" if info["ext"] in ("jpeg", "jpg") else info["ext"]
        path = OUT_DIR / f"{stem}.{ext}"
        path.write_bytes(info["image"])
    else:
        path = OUT_DIR / f"{stem}.png"
        path.write_bytes(render_page(pdf, page_num))
    return path.relative_to(DATA_DIR).as_posix()


pdf  = fitz.open(PDF_PATH)
conn = sqlite3.connect(DB_PATH)
rows = conn.execute(
    "SELECT id, nome, pagina_origem FROM products ORDER BY pagina_origem"
).fetchall()

# Cache de páginas já extraídas (evita reprocessar a mesma página)
page_cache: dict[int, str] = {}

def get_page_path(pdf, page_num, suffix):
    key = (page_num, suffix)
    if key not in page_cache:
        stem = f"pag{page_num:03d}_{suffix}"
        page_cache[key] = save_page_image(pdf, page_num, stem)
    return page_cache[key]


total = len(rows)
for i, (pid, nome, pag) in enumerate(rows, 1):
    p1, p2 = PRODUCT_OVERRIDES.get(pid, PAGE_PAIRS.get(pag, (pag, None)))

    rel1 = get_page_path(pdf, p1, "main")

    if p2 is not None:
        rel2 = get_page_path(pdf, p2, "tech")
        imgs = json.dumps([rel1, rel2])
    else:
        imgs = json.dumps([rel1])

    conn.execute(
        "UPDATE products SET imagem_path=?, imagens=? WHERE id=?",
        (rel1, imgs, pid)
    )
    status = f"{p1}+{p2}" if p2 else f"{p1}"
    print(f"  [{i:02d}/{total}] id={pid:3d}  pág={status:6s}  {nome}")

conn.commit()
conn.close()
pdf.close()
print(f"\nFeito. {total} produtos atualizados.")
print(f"Imagens em: {OUT_DIR}")

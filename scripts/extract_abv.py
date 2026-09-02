"""
Extrator completo para ABV 2025.pdf
- Limpa o banco
- 51 produtos, cada um em 2 páginas: par=ambiente, ímpar=técnica
- Extrai imagens em JPEG e especificações técnicas via texto do PDF
"""
import pymupdf as fitz
import sqlite3
import json
import re
from pathlib import Path

PDF_PATH  = r"C:\Users\joao.miguel\Documents\catalogos\catalogos 3\ABV 2025.pdf"
DB_PATH   = r"C:\Users\joao.miguel\Documents\csm-catalog-extractor\data\catalog.db"
DATA_DIR  = Path(r"C:\Users\joao.miguel\Documents\csm-catalog-extractor\data")
OUT_DIR   = DATA_DIR / "products" / "ABV 2025"
OUT_DIR.mkdir(parents=True, exist_ok=True)

FORNECEDOR = "ABV Design de Móveis"

# ─── Parsing de texto ─────────────────────────────────────────────────────────

def collapse_spaced(line: str) -> str:
    """
    Colapsa texto espaçado do PDF.
    'D U N A'       → 'DUNA'
    'M Ô N ACO'     → 'MÔNACO'   (tokens mistos 1-3 chars)
    'B E LL A'      → 'BELLA'
    'D o u r a d o + F o g' → 'Dourado + Fog'
    """
    tokens = line.strip().split(" ")
    non_empty = [t for t in tokens if t]
    if not non_empty:
        return line.strip()

    # Se comprimento médio dos tokens > 3, é texto normal — não colapsar
    avg_len = sum(len(t) for t in non_empty) / len(non_empty)
    if avg_len > 3:
        return line.strip()

    groups, cur = [], []
    for t in tokens:
        if not t:
            continue
        if t in "+-/|":
            if cur:
                groups.append("".join(cur))
                cur = []
            groups.append(t)
        else:
            cur.append(t)
    if cur:
        groups.append("".join(cur))
    return " ".join(groups)


def fix_dimension(s: str) -> str:
    """'P-115cmx45cmxh.70cm' → 'P - 115cm x 45cm x h.70cm'"""
    # garantir espaço após separador
    s = re.sub(r"^([A-Z])-", r"\1 - ", s)
    # separar 'cm' de próxima letra
    s = re.sub(r"cm([a-zA-Z])", r"cm \1", s)
    # espaço antes de dígito após 'x '
    s = re.sub(r"x(\d)", r"x \1", s)
    return s


def parse_tech_page(raw_text: str) -> dict:
    lines = raw_text.split("\n")

    # Filtrar boilerplate
    filtered = []
    for l in lines:
        l = l.strip()
        if not l:
            continue
        if re.match(r"^curvas", l, re.IGNORECASE):
            continue
        if l.isdigit():
            continue
        if re.match(r"^Refer[eê]", l, re.IGNORECASE):
            continue
        if re.match(r"^\*Imagens", l, re.IGNORECASE):
            continue
        filtered.append(l)

    collapsed = [collapse_spaced(l) for l in filtered]

    name = ""
    category = ""
    cores_list = []
    dim_list = []
    desc_parts = []

    for col in collapsed:
        s = col.strip()
        if not s:
            continue

        # Dimensão: letra maiúscula + hífen + número
        if re.match(r"^[A-Z] ?[-–] ?\d", s) or re.match(r"^[A-Z]-\d", s):
            dim_list.append(fix_dimension(s))
            continue

        # Cores: tem '+'
        if "+" in s:
            cores_list.append(s)
            continue

        # Nome: todas as letras do token colapsado são maiúsculas
        only_alpha = re.sub(r"[^A-Za-zÀ-ÖØ-öø-ÿ]", "", s)
        if only_alpha and only_alpha.upper() == only_alpha and len(only_alpha) >= 2:
            if not name:
                # Colapsar novamente para juntar quaisquer tokens residuais, depois title()
                collapsed_name = re.sub(r"\s+", "", s)  # remove espaços internos
                name = collapsed_name.title()
            continue

        # Categoria ou descrição: texto legível restante
        # A categoria tende a ser a última linha curta e sem números
        if s and not re.search(r"\d", s):
            category = s  # a última linha não-numérica vence

    # Cores flatten → lista de strings individuais (ex: ["Champagne", "Savana"])
    cores_flat = []
    for c in cores_list:
        for part in re.split(r"\s*\+\s*", c):
            part = part.strip()
            if part:
                cores_flat.append(part)

    return {
        "nome":       name,
        "categoria":  category,
        "descricao":  "",
        "dimensoes":  " | ".join(dim_list),
        "materiais":  json.dumps([]),
        "cores":      json.dumps(cores_flat),
        "paleta_hex": json.dumps([]),
    }


# ─── Extração de imagem ───────────────────────────────────────────────────────

def render_page(pdf, page_num: int, out_stem: str) -> str:
    """
    Renderiza a página INTEIRA exatamente como aparece no PDF.
    Retorna caminho relativo a DATA_DIR.
    """
    page = pdf[page_num - 1]
    mat = fitz.Matrix(2.2, 2.2)          # ~158 DPI — alta qualidade
    pix = page.get_pixmap(matrix=mat, alpha=False)
    out_path = Path(out_stem + ".jpg")
    pix.save(str(out_path), jpg_quality=95)
    return out_path.relative_to(DATA_DIR).as_posix()


# ─── Principal ────────────────────────────────────────────────────────────────

pdf  = fitz.open(PDF_PATH)
conn = sqlite3.connect(DB_PATH)

print("Limpando banco de dados...")
conn.execute("DELETE FROM products")
conn.execute("DELETE FROM ingestion_log")
conn.execute("DELETE FROM supplier_config")
conn.execute("DELETE FROM sqlite_sequence WHERE name='products'")
conn.execute("INSERT INTO products_fts(products_fts) VALUES('rebuild')")
conn.commit()

# Pares de páginas: 6-7, 8-9, ..., 106-107  (51 produtos)
product_pairs = [(n, n + 1) for n in range(6, 108, 2)]
print(f"Processando {len(product_pairs)} produtos (págs 6-107)...\n")

inserted = 0
for amb_pag, tech_pag in product_pairs:
    if tech_pag > len(pdf):
        break

    # ── Texto da página técnica ──────────────────────────────────────────
    tech_text = pdf[tech_pag - 1].get_text("text")
    fields    = parse_tech_page(tech_text)

    if not fields["nome"] and not fields["categoria"]:
        print(f"  [skip] pag {amb_pag}-{tech_pag}: sem dados legíveis")
        continue

    # ── Imagens ──────────────────────────────────────────────────────────
    stem1 = str(OUT_DIR / f"pag{amb_pag:03d}_amb")
    stem2 = str(OUT_DIR / f"pag{amb_pag:03d}_tech")

    img1 = render_page(pdf, amb_pag,  stem1)
    img2 = render_page(pdf, tech_pag, stem2)

    imagens = [i for i in [img1, img2] if i]

    # ── Inserir no banco ─────────────────────────────────────────────────
    conn.execute("""
        INSERT INTO products
          (nome, categoria, descricao, dimensoes, materiais, cores, paleta_hex,
           imagem_path, pagina_origem, pdf_origem, fornecedor, aprovado, imagens)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
    """, (
        fields["nome"],
        fields["categoria"],
        fields["descricao"],
        fields["dimensoes"],
        fields["materiais"],
        fields["cores"],
        fields["paleta_hex"],
        imagens[0] if imagens else "",
        amb_pag,
        PDF_PATH,
        FORNECEDOR,
        json.dumps(imagens),
    ))

    inserted += 1
    dim_short = fields["dimensoes"][:45] if fields["dimensoes"] else "—"
    print(f"  [{inserted:02d}] pág {amb_pag:03d}-{tech_pag:03d}  "
          f"{fields['categoria']:25s} {fields['nome']:20s}  {dim_short}")

# Registrar ingestão e reconstruir índice de busca
conn.execute("INSERT INTO ingestion_log VALUES (?, datetime('now'), ?)",
             ("ABV 2025", inserted))
conn.execute("INSERT INTO products_fts(products_fts) VALUES('rebuild')")
conn.commit()
conn.close()
pdf.close()

print(f"\nFeito! {inserted} produtos inseridos.")
print(f"  Imagens em: {OUT_DIR}")

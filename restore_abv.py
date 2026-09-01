"""
Restaura os produtos ABV 2025 no banco de dados.
Extrai nome/categoria/dimensões diretamente do PDF (sem API).
Usa as imagens já processadas em data/products/ABV 2025/.
"""
import re, json, sys, sqlite3, unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "webapp"))
from config import DB_PATH, DATA_DIR

PDF_PATH   = Path(r"C:\Users\joao.miguel\Documents\catalogos\catalogos 3\ABV 2025.pdf")
IMGS_DIR   = DATA_DIR / "products" / "ABV 2025"
FORNECEDOR = "ABV Design de Móveis"
PDF_ORIGEM = "ABV 2025"

# ── Mapa de categorias pelas faixas de páginas do índice ─────────────────────
CATEGORIA_RANGES = [
    (6,  19,  "Carrinho"),
    (20, 41,  "Mesa Lateral"),
    (42, 61,  "Mesa"),
    (62, 75,  "Cadeira"),
    (76, 91,  "Puf"),
    (92, 99,  "Luminária"),
    (100, 107, "Estante"),
]

def get_categoria(even_page: int) -> str:
    for start, end, cat in CATEGORIA_RANGES:
        if start <= even_page <= end:
            return cat
    return "Mobiliário"

def _ascii_upper(s: str) -> str:
    """Remove acentos e converte para maiúsculas: 'Mônaco' → 'MONACO'."""
    return unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode().upper()

# Chaves em ASCII puro (sem acentos) para comparação robusta
_NAME_FIX = {
    "MONACO":   "Mônaco",
    "RAVENA":   "Ravena",
    "ACAPULCO": "Acapulco",
    "CALABRIA": "Calábria",
    "ONIX":     "Ônix",
    "INDICE":   "",
}

def collapse_spaced(text: str) -> str:
    """
    Remove espaços entre caracteres individuais.
    'D U N A' → 'DUNA', 'Rav E N A' → 'RavENA' → 'Ravena'
    'M Ñ Aco' → 'MÑAco' → normaliza → 'MONACO' → 'Mônaco'
    Heurística: se ≥60% dos tokens têm ≤3 chars, colapsa tudo.
    """
    tokens = text.split()
    if len(tokens) < 2:
        return text
    short = sum(1 for t in tokens if len(t) <= 3)
    if short / len(tokens) >= 0.60:
        collapsed = "".join(tokens)
        # Normaliza para ASCII para lookup no mapa (lida com Ñ→N, Ô→O, etc.)
        key = _ascii_upper(re.sub(r'[^A-Za-zÀ-ÿ]', '', collapsed))
        for k, v in _NAME_FIX.items():
            if k in key:
                return v
        return collapsed.title()
    return text

def normalize_dim_line(raw_line: str) -> str:
    """
    Converte linha de dimensão com chars espaçados para formato normal.
    'P - 1 1 5 c m x 4 5 c m x h . 7 0 c m' → 'P - 115cm x 45cm x h.70cm'
    """
    # Remove espaços ENTRE dígitos e ENTRE letras de unidade (cm, Ø, etc.)
    # Estratégia: colapsa runs de (char + espaço) onde chars são dígitos/letras/pontos/Ø
    s = raw_line.strip()
    # Colapsa sequências de "X " onde X é char de unidade ou dígito
    s = re.sub(r'(?<=[a-zA-Z0-9ØøÂÃÁÉÍÓÚ,.])\s(?=[a-zA-Z0-9ØøÂÃÁÉÍÓÚ,.])', '', s)
    # Garante espaço antes e depois de 'x' como multiplicador
    s = re.sub(r'(?<=[0-9cm,])x(?=[0-9hHØø])', ' x ', s)
    s = re.sub(r'(?<=[0-9cm,])\s*x\s*(?=[0-9hHØø])', ' x ', s)
    # Garante espaço após hífen do tamanho
    s = re.sub(r'^([A-Z][A-Z0-9]*(?:\s+[A-Z][A-Z0-9]*)*)\s*[-–]\s*', r'\1 - ', s)
    # Normaliza h. e Ø
    s = re.sub(r'h\s*\.\s*', 'h.', s)
    s = re.sub(r'[Øø]\s*', 'Ø', s)
    return s.strip()

def parse_page_text(raw: str) -> dict:
    """Extrai nome, dimensões e cores do texto bruto de uma página spec."""
    lines = [l.strip() for l in raw.splitlines() if l.strip()]

    # Remove cabeçalho/rodapé
    lines = [l for l in lines
             if "curvas & contornos" not in l.lower()
             and not re.match(r'^\d+$', l)
             and "referência na imagem" not in l.lower()
             and "referencia na imagem" not in l.lower()
             and l.lower() not in ("índice", "indice", "acabamentos", "catálogo", "catalogo")]

    # Colapsa linhas com chars espaçados
    collapsed = [collapse_spaced(l) for l in lines]

    # ── Nome ─────────────────────────────────────────────────────────────────
    # Linha toda em maiúsculas (ou maiúsculas após colapso) sem dígitos/hífens
    nome = ""
    for c in collapsed:
        c_stripped = c.strip()
        if (c_stripped.upper() == c_stripped          # MAIÚSCULAS
                and len(c_stripped) >= 2
                and not re.search(r'[\d\-–x×]', c_stripped)
                and not any(w in c_stripped.lower() for w in
                            ["índice", "catálogo", "acabamentos"])):
            nome = c_stripped.title()
            break
    if not nome:
        # Fallback: primeira linha longa que parece nome (sem dígitos)
        for c in collapsed:
            if len(c) >= 3 and not re.search(r'[\d\-–]', c) and not re.search(r'\s{2,}', c):
                nome = c.strip().title()
                break

    # ── Dimensões ─────────────────────────────────────────────────────────────
    dim_parts = []
    for raw_line in lines:
        # Detecta linha de dimensão: começa com código de tamanho e hífen
        if re.match(r'^[A-Z][A-Z0-9 ]*\s*[-–]', raw_line):
            norm = normalize_dim_line(raw_line)
            if norm:
                dim_parts.append(norm)
    dimensoes = " | ".join(dim_parts)

    # ── Cores ─────────────────────────────────────────────────────────────────
    cores = []
    for raw_line in lines:
        c = collapse_spaced(raw_line)
        if '+' in c and not re.search(r'[\d\-–]', c):
            partes = [p.strip() for p in c.split('+')]
            cores = [p for p in partes if p and len(p) >= 2]
            break

    return {"nome": nome, "dimensoes": dimensoes, "cores": cores}

def main():
    import pymupdf
    doc = pymupdf.open(str(PDF_PATH))
    print(f"PDF: {len(doc)} páginas")

    # Lista imagens existentes por número de página
    img_files = list(IMGS_DIR.glob("pag*_amb.jpg"))
    even_pages = sorted({
        int(re.search(r'pag(\d+)_', f.name).group(1))
        for f in img_files
        if re.search(r'pag(\d+)_', f.name)
    })
    print(f"Imagens encontradas para {len(even_pages)} produtos: páginas {even_pages[:5]}...")

    products = []
    for even_pg in even_pages:
        odd_pg = even_pg - 1   # página ímpar = specs

        # Imagens deste produto
        amb_rel  = f"products/ABV 2025/pag{even_pg:03d}_amb.jpg"
        tech_rel = f"products/ABV 2025/pag{even_pg:03d}_tech.jpg"
        imagens  = []
        if (DATA_DIR / amb_rel).exists():
            imagens.append(amb_rel)
        if (DATA_DIR / tech_rel).exists():
            imagens.append(tech_rel)

        # Extrai texto da página spec (ímpar, 0-indexed)
        nome, dimensoes, cores = "", "", []
        if 0 <= odd_pg - 1 < len(doc):
            raw = doc[odd_pg - 1].get_text("text")
            parsed = parse_page_text(raw)
            nome      = parsed["nome"]
            dimensoes = parsed["dimensoes"]
            cores     = parsed["cores"]

        # Fallback de nome: usa número da página
        if not nome:
            nome = f"Produto ABV pág.{even_pg}"

        categoria = get_categoria(even_pg)
        products.append({
            "nome": nome,
            "categoria": categoria,
            "dimensoes": dimensoes,
            "cores": cores,
            "imagens": imagens,
            "pagina_origem": even_pg,
        })
        print(f"  pág{even_pg:03d} | {nome:<30} | {categoria:<15} | dims={dimensoes[:35]}")

    doc.close()

    # ── Insere no banco ───────────────────────────────────────────────────────
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")

    # Limpa entradas antigas deste PDF
    conn.execute("DELETE FROM products WHERE pdf_origem = ?", (PDF_ORIGEM,))
    conn.execute("DELETE FROM ingestion_log WHERE pdf_name = ?", (PDF_ORIGEM,))

    inserted = 0
    for p in products:
        conn.execute("""
            INSERT INTO products
                (nome, categoria, descricao, dimensoes, materiais, cores,
                 paleta_hex, imagem_path, imagens, pagina_origem,
                 pdf_origem, fornecedor, aprovado)
            VALUES (?, ?, '', ?, '[]', ?, '[]', '', ?, ?, ?, ?, 1)
        """, (
            p["nome"],
            p["categoria"],
            p["dimensoes"],
            json.dumps(p["cores"], ensure_ascii=False),
            json.dumps(p["imagens"], ensure_ascii=False),
            p["pagina_origem"],
            PDF_ORIGEM,
            FORNECEDOR,
        ))
        inserted += 1

    conn.execute("INSERT INTO ingestion_log (pdf_name, total) VALUES (?, ?)",
                 (PDF_ORIGEM, inserted))
    conn.execute("INSERT INTO products_fts(products_fts) VALUES('rebuild')")
    conn.commit()
    conn.close()
    print(f"\n✓ {inserted} produtos restaurados no banco de dados.")

if __name__ == "__main__":
    main()

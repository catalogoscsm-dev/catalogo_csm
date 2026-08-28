"""
renderizar_pdfs.py
Converte cada página de todos os PDFs em PNG perfeito.
Roda antes da extração manual ou automática.

Uso:
    .venv\\Scripts\\python.exe scripts\\renderizar_pdfs.py

Os PNGs ficam em:  data\\preview\\<nome_do_pdf>\\pag001.png, pag002.png ...
"""
from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "src"))

try:
    import pymupdf as fitz
except ImportError:
    import fitz

# ── Configuração ──────────────────────────────────────────────────────────────

# Pasta com os PDFs originais
PDF_DIR = Path(r"C:\Users\joao.miguel\Documents\catalogos\catalogos 3")

# Onde os PNGs serão salvos
PREVIEW_DIR = ROOT / "data" / "preview"

# Qualidade: 1.5 = 72dpi→108dpi (leve), 2.0 = 144dpi (bom), 3.0 = 216dpi (pesado)
ZOOM = 1.5

# Processar apenas PDFs ainda não renderizados (True = pula se pasta já existe)
PULAR_JA_FEITOS = True

# ── Execução ──────────────────────────────────────────────────────────────────

def renderizar(pdf_path: Path, saida_dir: Path, zoom: float) -> int:
    mat = fitz.Matrix(zoom, zoom)
    doc = fitz.open(str(pdf_path))
    saida_dir.mkdir(parents=True, exist_ok=True)

    for i, page in enumerate(doc, start=1):
        dest = saida_dir / f"pag{i:03d}.png"
        if dest.exists():
            continue
        pix = page.get_pixmap(matrix=mat, alpha=False)
        pix.save(str(dest))

    doc.close()
    return len(list(saida_dir.glob("pag*.png")))


def main() -> None:
    pdfs = sorted(PDF_DIR.glob("*.pdf"))
    if not pdfs:
        print(f"Nenhum PDF encontrado em {PDF_DIR}")
        return

    print(f"{len(pdfs)} PDF(s) encontrado(s)\n")

    for pdf in pdfs:
        saida = PREVIEW_DIR / pdf.stem
        if PULAR_JA_FEITOS and saida.exists() and any(saida.glob("pag*.png")):
            n = len(list(saida.glob("pag*.png")))
            print(f"  [PULADO]  {pdf.name:<50}  ({n} páginas já renderizadas)")
            continue

        print(f"  Renderizando  {pdf.name} ...", end="", flush=True)
        try:
            n = renderizar(pdf, saida, ZOOM)
            print(f"  {n} paginas -> {saida}")
        except Exception as e:
            print(f"  ERRO: {e}")

    print("\nConcluido. PNGs em:", PREVIEW_DIR)


if __name__ == "__main__":
    main()

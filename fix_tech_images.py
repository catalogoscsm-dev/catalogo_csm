"""
Re-renderiza todas as imagens tecnicas ABV a partir das paginas correctas do PDF.

Problema: o extractor original guardou pag{N}_tech.jpg a partir da pagina N+1 (spec do
produto SEGUINTE). A pagina de specs correcta e N-1 (a pagina impar anterior).

Fix: para cada produto (pag{N}), renderiza doc[N-2] (= PDF pagina N-1) e guarda como
pag{N}_tech.jpg. Limpa tambem o cache de marcas d'agua.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "webapp"))
from config import DATA_DIR

PDF_PATH = Path(r"C:\Users\joao.miguel\Documents\catalogos\catalogos 3\ABV 2025.pdf")
IMGS_DIR = DATA_DIR / "products" / "ABV 2025"
WM_CACHE = DATA_DIR / "watermarked"

import pymupdf, hashlib

doc = pymupdf.open(str(PDF_PATH))
print(f"PDF aberto: {len(doc)} paginas")

# Todos os produtos excepto pag006 (cuja pagina de specs e o indice)
even_pages = list(range(8, 108, 2))   # 8, 10, 12, ... 106

updated = 0
for even_pg in even_pages:
    spec_0idx = even_pg - 2          # doc[even_pg-2] == PDF pagina (even_pg-1)
    if spec_0idx < 0 or spec_0idx >= len(doc):
        print(f"  pag{even_pg:03d}: SKIP (fora do intervalo)")
        continue

    out_path = IMGS_DIR / f"pag{even_pg:03d}_tech.jpg"

    page = doc[spec_0idx]
    # Renderiza a 2x para boa qualidade (~150 dpi para uma pagina A4)
    mat  = pymupdf.Matrix(2.0, 2.0)
    pix  = page.get_pixmap(matrix=mat, colorspace=pymupdf.csRGB)
    pix.save(str(out_path), jpg_quality=90)

    size_kb = out_path.stat().st_size // 1024
    print(f"  pag{even_pg:03d}: PDF p.{even_pg-1} -> {out_path.name} ({size_kb} KB)")
    updated += 1

    # Invalida cache de marca d'agua para esta imagem
    subpath = f"products/ABV 2025/pag{even_pg:03d}_tech.jpg"
    cache_key = hashlib.md5(subpath.encode()).hexdigest() + ".jpg"
    cache_path = WM_CACHE / cache_key
    if cache_path.exists():
        cache_path.unlink()
        print(f"           cache invalidado: {cache_key}")

doc.close()
print(f"\n{updated} imagens tecnicas re-renderizadas.")

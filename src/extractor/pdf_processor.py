from __future__ import annotations
import fitz  # PyMuPDF
from pathlib import Path
from dataclasses import dataclass


@dataclass
class PaginaImagem:
    numero: int
    caminho: Path
    largura_px: int
    altura_px: int


class PDFProcessor:
    """
    Converte páginas de PDF em imagens PNG de alta resolução.
    Usa PyMuPDF (fitz) — sem dependência de Poppler.
    """

    def __init__(self, dpi: int = 200):
        self.dpi = dpi
        # fitz usa fator de zoom: 72 DPI é o padrão interno
        self.zoom = dpi / 72.0

    def converter_pdf(self, pdf_path: Path, output_dir: Path) -> list[PaginaImagem]:
        """
        Converte todas as páginas de um PDF em PNGs.
        Retorna lista de PaginaImagem com caminho e dimensões.
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        paginas: list[PaginaImagem] = []

        doc = fitz.open(str(pdf_path))
        nome_base = pdf_path.stem

        for i, page in enumerate(doc):
            numero = i + 1
            matrix = fitz.Matrix(self.zoom, self.zoom)
            pixmap = page.get_pixmap(matrix=matrix, alpha=False)

            caminho_saida = output_dir / f"{nome_base}_pag{numero:03d}.png"
            pixmap.save(str(caminho_saida))

            paginas.append(PaginaImagem(
                numero=numero,
                caminho=caminho_saida,
                largura_px=pixmap.width,
                altura_px=pixmap.height,
            ))

        doc.close()
        return paginas

    def converter_pagina(self, pdf_path: Path, numero_pagina: int, output_dir: Path) -> PaginaImagem:
        """Converte uma página específica (1-indexed)."""
        output_dir.mkdir(parents=True, exist_ok=True)
        doc = fitz.open(str(pdf_path))
        nome_base = pdf_path.stem

        page = doc[numero_pagina - 1]
        matrix = fitz.Matrix(self.zoom, self.zoom)
        pixmap = page.get_pixmap(matrix=matrix, alpha=False)

        caminho_saida = output_dir / f"{nome_base}_pag{numero_pagina:03d}.png"
        pixmap.save(str(caminho_saida))
        doc.close()

        return PaginaImagem(
            numero=numero_pagina,
            caminho=caminho_saida,
            largura_px=pixmap.width,
            altura_px=pixmap.height,
        )

    def total_paginas(self, pdf_path: Path) -> int:
        doc = fitz.open(str(pdf_path))
        n = doc.page_count
        doc.close()
        return n

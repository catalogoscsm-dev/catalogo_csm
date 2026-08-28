from __future__ import annotations
from pathlib import Path

from PIL import Image

from .models import BoundingBox


class ImageCropper:
    """
    Recorta imagens de produtos a partir de bounding boxes retornados
    pela IA de visão. Usa Pillow.
    """

    # Margem extra em % para garantir que o produto inteiro é capturado
    MARGEM = 0.01

    def recortar(
        self,
        imagem_original: Path,
        bbox: BoundingBox,
        output_path: Path,
        qualidade: int = 95,
    ) -> Path:
        """
        Recorta a região do produto na imagem e salva em output_path.
        Retorna o caminho do arquivo salvo.
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with Image.open(imagem_original) as img:
            w, h = img.size

            # Aplica margem extra e clamp nos limites da imagem
            left   = max(0, int((bbox.x - self.MARGEM) * w))
            top    = max(0, int((bbox.y - self.MARGEM) * h))
            right  = min(w, int((bbox.x + bbox.largura + self.MARGEM) * w))
            bottom = min(h, int((bbox.y + bbox.altura + self.MARGEM) * h))

            # Sanity check: bbox inválido → usa imagem inteira
            if right <= left or bottom <= top:
                recorte = img
            else:
                recorte = img.crop((left, top, right, bottom))

            # Salva sempre como JPEG para economizar espaço no tablet
            if output_path.suffix.lower() in (".jpg", ".jpeg"):
                recorte.save(str(output_path), "JPEG", quality=qualidade, optimize=True)
            else:
                recorte.save(str(output_path), "PNG", optimize=True)

        return output_path

    def recortar_pagina_inteira(self, imagem: Path, output_path: Path) -> Path:
        """Copia a imagem inteira como produto (sem recorte)."""
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with Image.open(imagem) as img:
            img.save(str(output_path), "JPEG", quality=90, optimize=True)

        return output_path

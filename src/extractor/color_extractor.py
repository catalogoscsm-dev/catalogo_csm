from __future__ import annotations
from pathlib import Path

from colorthief import ColorThief


class ColorExtractor:
    """
    Extrai as cores dominantes de uma imagem de produto.
    Usa ColorThief — algoritmo de quantização de cores (MMCQ).
    """

    def __init__(self, num_cores: int = 5, qualidade: int = 1):
        """
        num_cores: quantas cores dominantes extrair (padrão: 5)
        qualidade: 1 = melhor qualidade, maior = mais rápido
        """
        self.num_cores = num_cores
        self.qualidade = qualidade

    def extrair_paleta(self, imagem_path: Path) -> list[str]:
        """
        Retorna lista de cores em formato hex (#RRGGBB).
        A primeira cor é a mais dominante.
        """
        try:
            thief = ColorThief(str(imagem_path))

            if self.num_cores == 1:
                rgb = thief.get_color(quality=self.qualidade)
                return [self._rgb_to_hex(rgb)]

            palette = thief.get_palette(
                color_count=self.num_cores,
                quality=self.qualidade,
            )
            return [self._rgb_to_hex(cor) for cor in palette]

        except Exception as e:
            print(f"  Aviso ColorThief ({imagem_path.name}): {e}")
            return []

    def _rgb_to_hex(self, rgb: tuple[int, int, int]) -> str:
        return "#{:02X}{:02X}{:02X}".format(*rgb)

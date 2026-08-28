from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
from enum import Enum


class StatusRevisao(str, Enum):
    PENDENTE = "pendente"
    APROVADO = "aprovado"
    REJEITADO = "rejeitado"
    ERRO = "erro"


@dataclass
class ParteMulticolor:
    parte: str
    opcoes: list[str]


@dataclass
class BoundingBox:
    """Coordenadas em percentual da imagem (0.0 a 1.0)"""
    x: float
    y: float
    largura: float
    altura: float

    def is_valid(self) -> bool:
        return not (self.x == 0 and self.y == 0 and self.largura == 0 and self.altura == 0)

    def to_pixel_coords(self, img_width: int, img_height: int) -> tuple[int, int, int, int]:
        """Retorna (left, top, right, bottom) em pixels"""
        left   = int(self.x * img_width)
        top    = int(self.y * img_height)
        right  = int((self.x + self.largura) * img_width)
        bottom = int((self.y + self.altura) * img_height)
        return left, top, right, bottom


@dataclass
class Produto:
    nome: str
    categoria: str
    descricao: str
    dimensoes: str
    materiais: list[str]
    cores_disponiveis: list[str]
    partes_multicolor: list[ParteMulticolor]
    bbox: BoundingBox

    # Preenchido após recorte e extração de cor
    imagem_path: Optional[str] = None
    paleta_hex: list[str] = field(default_factory=list)

    # Metadados de origem
    pagina_origem: int = 0
    pdf_origem: str = ""
    fornecedor_interno: str = ""

    # Controle de revisão
    status_revisao: StatusRevisao = StatusRevisao.PENDENTE
    aprovado: bool = False
    notas_revisao: str = ""

    def to_dict(self) -> dict:
        return {
            "nome": self.nome,
            "categoria": self.categoria,
            "descricao": self.descricao,
            "dimensoes": self.dimensoes,
            "materiais": self.materiais,
            "cores_disponiveis": self.cores_disponiveis,
            "partes_multicolor": [
                {"parte": p.parte, "opcoes": p.opcoes}
                for p in self.partes_multicolor
            ],
            "bbox": {
                "x": self.bbox.x,
                "y": self.bbox.y,
                "largura": self.bbox.largura,
                "altura": self.bbox.altura,
            },
            "imagem_path": self.imagem_path,
            "paleta_hex": self.paleta_hex,
            "pagina_origem": self.pagina_origem,
            "pdf_origem": self.pdf_origem,
            "fornecedor_interno": self.fornecedor_interno,
            "status_revisao": self.status_revisao.value,
            "aprovado": self.aprovado,
            "notas_revisao": self.notas_revisao,
        }


@dataclass
class ResultadoPagina:
    pagina: int
    pdf_origem: str
    produtos: list[Produto]
    multiplos_na_pagina: bool
    erro: Optional[str] = None
    bbox_detectado: bool = False


@dataclass
class ResultadoPDF:
    pdf_path: str
    fornecedor: str
    total_paginas: int
    paginas_processadas: int = 0
    produtos: list[Produto] = field(default_factory=list)
    erros: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "pdf_path": self.pdf_path,
            "fornecedor": self.fornecedor,
            "total_paginas": self.total_paginas,
            "paginas_processadas": self.paginas_processadas,
            "total_produtos": len(self.produtos),
            "produtos": [p.to_dict() for p in self.produtos],
            "erros": self.erros,
        }

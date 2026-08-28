from __future__ import annotations
import json
from pathlib import Path
from datetime import datetime


class Checkpoint:
    """
    Salva e carrega o progresso de processamento de um PDF.
    Permite retomar de onde parou em caso de interrupção.
    Salva a cada N páginas (configurável).
    """

    def __init__(self, checkpoint_dir: Path, pdf_name: str, salvar_a_cada: int = 10):
        self.checkpoint_dir = checkpoint_dir
        self.pdf_name = pdf_name
        self.salvar_a_cada = salvar_a_cada
        self.caminho = checkpoint_dir / f"{pdf_name}.checkpoint.json"
        checkpoint_dir.mkdir(parents=True, exist_ok=True)

    def existe(self) -> bool:
        return self.caminho.exists()

    def salvar(self, ultima_pagina: int, produtos_acumulados: list[dict]) -> None:
        dados = {
            "pdf_name": self.pdf_name,
            "ultima_pagina_processada": ultima_pagina,
            "total_produtos_ate_agora": len(produtos_acumulados),
            "produtos": produtos_acumulados,
            "salvo_em": datetime.now().isoformat(),
        }
        with open(self.caminho, "w", encoding="utf-8") as f:
            json.dump(dados, f, ensure_ascii=False, indent=2)

    def carregar(self) -> dict:
        with open(self.caminho, "r", encoding="utf-8") as f:
            return json.load(f)

    def deletar(self) -> None:
        if self.caminho.exists():
            self.caminho.unlink()

    def deve_salvar(self, pagina_atual: int) -> bool:
        return pagina_atual % self.salvar_a_cada == 0

#!/usr/bin/env python3
"""
Script COMPLETO — processa todos os 121 PDFs.
Execute apenas após validar o piloto (run_pilot.py).

USO:
  python scripts/run_full.py

PDFs em: data/pdfs/
Resultados em: data/output/
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from extractor import Pipeline

load_dotenv()

CLAUDE_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

DIR_BASE   = Path(__file__).parent.parent
DIR_PDFS   = DIR_BASE / "data" / "pdfs"
DIR_OUTPUT = DIR_BASE / "data" / "output"
DIR_CKPT   = DIR_BASE / "data" / "checkpoints"

# ── Mapeamento de fornecedores (preencha antes de rodar!) ─────────────────
# Formato: "nome-do-arquivo-sem-extensao": "Nome Interno do Fornecedor"
# O nome do fornecedor NÃO aparece para o cliente no app — é apenas interno.
FORNECEDORES: dict[str, str] = {
    # Exemplo:
    # "catalogo-abc-2024": "Fornecedor ABC",
    # "moveis-xyz-linha-premium": "Fornecedor XYZ",
}
# ─────────────────────────────────────────────────────────────────────────


def main():
    if not CLAUDE_API_KEY:
        print("❌ Configure ANTHROPIC_API_KEY no .env")
        sys.exit(1)

    # Ignora pasta 'piloto' para não reprocessar
    pdfs = sorted([
        p for p in DIR_PDFS.glob("*.pdf")
        if "piloto" not in str(p)
    ])

    if not pdfs:
        print(f"❌ Nenhum PDF encontrado em: {DIR_PDFS}")
        sys.exit(1)

    print(f"🚀 Processamento completo: {len(pdfs)} PDFs encontrados")
    confirmacao = input(f"Confirmar processamento de {len(pdfs)} PDFs? (s/n): ")
    if confirmacao.lower() not in ("s", "sim", "y", "yes"):
        print("Cancelado.")
        sys.exit(0)

    pipeline = Pipeline(
        claude_api_key=CLAUDE_API_KEY,
        output_dir=DIR_OUTPUT,
        checkpoint_dir=DIR_CKPT,
        dpi=200,
        num_cores_paleta=5,
        delay_entre_paginas=1.5,
    )

    pipeline.processar_lote(pdfs, fornecedores=FORNECEDORES)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Script de PILOTO — processa 5 PDFs para validar qualidade antes dos 121.

USO:
  python scripts/run_pilot.py

Coloque os 5 PDFs piloto em: data/pdfs/piloto/
O script gera resultados em: data/output/piloto/
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Adiciona o src ao path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from extractor import Pipeline

load_dotenv()

# ── Configuração ──────────────────────────────────────────────────────────
CLAUDE_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

DIR_BASE      = Path(__file__).parent.parent
DIR_PDFS      = DIR_BASE / "data" / "pdfs" / "piloto"
DIR_OUTPUT    = DIR_BASE / "data" / "output" / "piloto"
DIR_CKPT      = DIR_BASE / "data" / "checkpoints"

# ── Fornecedores (opcional — mapeia nome-do-arquivo → nome interno) ───────
# Edite conforme seus PDFs piloto reais
FORNECEDORES = {
    # "nome-do-arquivo-sem-extensao": "Nome Interno do Fornecedor",
    # Exemplo:
    # "catalogo-moveis-abc": "Fornecedor ABC",
}

# ─────────────────────────────────────────────────────────────────────────


def main():
    if not CLAUDE_API_KEY:
        print("❌ ANTHROPIC_API_KEY não definida no .env")
        sys.exit(1)

    DIR_PDFS.mkdir(parents=True, exist_ok=True)

    pdfs = sorted(DIR_PDFS.glob("*.pdf"))

    if not pdfs:
        print(f"❌ Nenhum PDF encontrado em: {DIR_PDFS}")
        print(f"   Coloque os 5 PDFs piloto nessa pasta e rode novamente.")
        sys.exit(1)

    if len(pdfs) > 5:
        print(f"⚠  Encontrados {len(pdfs)} PDFs. O piloto deve ter no máximo 5.")
        print(f"   Processando apenas os 5 primeiros.")
        pdfs = pdfs[:5]

    print(f"🚀 Iniciando piloto com {len(pdfs)} PDF(s)")
    for p in pdfs:
        print(f"   • {p.name}")

    pipeline = Pipeline(
        claude_api_key=CLAUDE_API_KEY,
        output_dir=DIR_OUTPUT,
        checkpoint_dir=DIR_CKPT,
        dpi=200,
        num_cores_paleta=5,
        delay_entre_paginas=1.2,
    )

    resultados = pipeline.processar_lote(pdfs, fornecedores=FORNECEDORES)

    # Resumo no terminal
    print("\n\n" + "="*60)
    print("RESUMO DO PILOTO")
    print("="*60)
    total = 0
    for r in resultados:
        n = len(r.produtos)
        total += n
        status = "✅" if n > 0 else "⚠ "
        print(f"  {status} {Path(r.pdf_path).name}: {n} produto(s), {r.paginas_processadas}/{r.total_paginas} páginas")

    print(f"\n  Total geral: {total} produto(s)")
    print(f"  Resultados em: {DIR_OUTPUT}")
    print("\nPróximo passo: revise os JSONs gerados e valide a qualidade.")
    print("Se OK, rode scripts/run_full.py para processar todos os 121 PDFs.\n")


if __name__ == "__main__":
    main()

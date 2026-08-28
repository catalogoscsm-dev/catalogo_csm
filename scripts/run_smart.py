"""
run_smart.py — Pipeline inteligente para catálogos heterogêneos.

Uso:
    .venv\Scripts\python.exe scripts\run_smart.py

Coloque os PDFs em data\pdfs\  (ou subpasta configurada abaixo).
Os resultados vão para data\output\<nome_pdf>\resultado_*.json
"""
from __future__ import annotations
import os
import sys
from pathlib import Path

# Permite rodar sem instalar o pacote
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "src"))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

from extractor.smart_pipeline import SmartPipeline

# ── Configuração ──────────────────────────────────────────────────────────────

CLAUDE_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

# Pasta com os PDFs a processar
PDF_DIR = ROOT / "data" / "pdfs"

# Mapeamento opcional: nome-do-arquivo → nome-do-fornecedor-interno
# (visível apenas para admins no webapp)
FORNECEDORES: dict[str, str] = {
    # "ABV 2025": "ABV Móveis",
    # "Aco Mobilia 2025-7": "Aço Mobilia",
    # Adicione conforme necessário — o stem do arquivo é a chave
}

# Pastas de saída
OUTPUT_DIR     = ROOT / "data" / "output"
CHECKPOINT_DIR = ROOT / "data" / "checkpoints"

# ── Execução ──────────────────────────────────────────────────────────────────

def main() -> None:
    if not CLAUDE_API_KEY:
        print("❌ ANTHROPIC_API_KEY não definida no .env")
        sys.exit(1)

    pdfs = sorted(PDF_DIR.glob("**/*.pdf"))
    if not pdfs:
        print(f"❌ Nenhum PDF encontrado em {PDF_DIR}")
        sys.exit(1)

    print(f"📂 {len(pdfs)} PDF(s) encontrado(s) em {PDF_DIR}")

    pipeline = SmartPipeline(
        claude_api_key=CLAUDE_API_KEY,
        output_dir=OUTPUT_DIR,
        checkpoint_dir=CHECKPOINT_DIR,
        dpi=150,
        delay_entre_paginas=0.8,
    )

    total_produtos = 0
    erros: list[str] = []

    for pdf_path in pdfs:
        fornecedor = FORNECEDORES.get(pdf_path.stem, pdf_path.stem)
        try:
            resultado = pipeline.processar_pdf(pdf_path, fornecedor=fornecedor)
            n = len(resultado.get("produtos", []))
            total_produtos += n
            print(f"  ✓ {pdf_path.name}: {n} produto(s)\n")
        except KeyboardInterrupt:
            print("\n⚠  Processamento interrompido pelo usuário.")
            break
        except Exception as e:
            msg = f"❌ Erro em {pdf_path.name}: {e}"
            print(msg)
            erros.append(msg)

    print(f"\n{'='*60}")
    print(f"Total de produtos extraídos: {total_produtos}")
    if erros:
        print(f"Erros ({len(erros)}):")
        for e in erros:
            print(f"  {e}")
    print(f"{'='*60}")
    print("\nAcesse /admin/reingest no webapp para importar os novos produtos.")


if __name__ == "__main__":
    main()

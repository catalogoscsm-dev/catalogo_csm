# CSM Catalog Extractor

Pipeline de extração de catálogos de móveis planejados — **arquitetura híbrida** Claude Vision + DeepSeek.

## Fluxo

```
PDF → PyMuPDF (imagens) → Claude Vision (bboxes) → Pillow (recorte) → DeepSeek (dados) → ColorThief (paleta) → JSON
```

## Instalação

```bash
# 1. Clone / copie o projeto
cd csm-catalog-extractor

# 2. Crie o ambiente virtual
python -m venv .venv
source .venv/bin/activate   # Linux/Mac
# .venv\Scripts\activate    # Windows

# 3. Instale as dependências
pip install -e .

# 4. Configure as chaves de API
cp .env.example .env
# Edite o .env e coloque suas chaves
```

## Configuração do .env

```
ANTHROPIC_API_KEY=sk-ant-...      # sua chave Claude
DEEPSEEK_API_KEY=sk-...            # sua chave DeepSeek
```

## Uso

### Piloto (5 PDFs para validação)

```bash
# 1. Coloque os 5 PDFs piloto em:
#    data/pdfs/piloto/

# 2. Rode o piloto
python scripts/run_pilot.py

# 3. Revise os resultados em:
#    data/output/piloto/
```

### Processamento completo (121 PDFs)

```bash
# 1. Coloque todos os PDFs em:
#    data/pdfs/

# 2. (Opcional) Edite o dict FORNECEDORES em run_full.py
#    para mapear nome do arquivo → nome interno do fornecedor

# 3. Rode o processamento completo
python scripts/run_full.py
```

## Estrutura de saída

```
data/output/
└── nome-do-pdf/
    ├── paginas/                   # Imagens PNG de cada página
    │   ├── nome-do-pdf_pag001.png
    │   └── ...
    ├── produtos/                  # Imagens recortadas por produto
    │   ├── nome-do-pdf_pag001_prod01.jpg
    │   └── ...
    └── resultado_YYYYMMDD_HHMMSS.json   # Dados de todos os produtos
```

## Estrutura do JSON por produto

```json
{
  "nome": "Mesa Athenas",
  "categoria": "Sala de Jantar",
  "descricao": "Mesa com estrutura em metalon...",
  "dimensoes": "76cm altura; 120x270, 110x240...",
  "materiais": ["Metalon 30x30", "Pintura eletrostática a pó"],
  "cores_disponiveis": ["Black", "Champagne", "Fendi"],
  "partes_multicolor": [
    {"parte": "Estrutura", "opcoes": ["Black", "Champagne"]},
    {"parte": "Tampo", "opcoes": ["MDF c/ Vidro Off White", "Laminado Cinamomo"]}
  ],
  "bbox": {"x": 0.0, "y": 0.0, "largura": 1.0, "altura": 1.0},
  "imagem_path": "nome-do-pdf/produtos/nome-do-pdf_pag001_prod01.jpg",
  "paleta_hex": ["#3D3D3D", "#F5F0E8", "#8B6914"],
  "pagina_origem": 1,
  "pdf_origem": "nome-do-pdf.pdf",
  "fornecedor_interno": "Fornecedor ABC",
  "status_revisao": "pendente",
  "aprovado": false
}
```

## Retomada automática

Se o processamento for interrompido (Ctrl+C, queda de energia, etc.),
rode o mesmo script novamente. O checkpoint retoma automaticamente
de onde parou.

## Custo estimado

- Claude Vision (Sonnet): ~$0.003–0.006 por página
- DeepSeek: ~$0.001–0.002 por produto
- 121 PDFs × ~25 páginas = ~3.000 páginas → **total ~$9–18 USD**

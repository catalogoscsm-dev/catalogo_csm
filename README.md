# CSM Decor — Catálogo Digital

Aplicação web interna para a equipa de vendas da **Campinas Shopping Móveis** consultar o catálogo de produtos extraído de PDFs de fornecedores.

---

## Funcionalidades actuais

### Catálogo (webapp Flask)
- **Login com dois níveis de acesso** — `admin` (acesso total) e `cliente` (só leitura)
- **Busca inteligente** — suporta plurais, acentos e erros ortográficos via FTS5 + stemmer português + fallback LIKE
- **Grid de produtos** — 5 colunas, cards com hover overlay (categoria, nome, dimensões)
- **Filtro por categoria** — dropdown que recarrega automaticamente
- **Paginação** — 24 produtos por página
- **Zoom tipo lupa** — passa o mouse sobre a imagem e abre painel lateral com zoom ampliado; clique abre lightbox fullscreen
- **Tema Light / Dark** — toggle na navbar com persistência em `localStorage`; efeito spotlight laranja no topo
- **Logo CSM** — presente na navbar, no PDF exportado e como marca d'água nas imagens

### Exportação de PDF
- Admin selecciona produtos no catálogo → botão flutuante "Exportar PDF"
- **Capa** — logo centrado, linhas decorativas laranja, título, subtítulo, data e contagem
- **2 páginas por produto:**
  - **Pág. 1** — foto principal em fullpage com header discreto (categoria + nome + linha laranja)
  - **Pág. 2** — foto(s) secundária(s) na metade superior + especificações técnicas na metade inferior
    - Tabela de dimensões (Tamanho / Largura / Profundidade / Altura)
    - Acabamentos / cores com **círculos degradê** individuais por cor (branco → cinza → carvalho → wengue etc.)
    - Fornecedor
- Marca d'água do logo CSM em todas as imagens
- Gerado via `fpdf2` + `Pillow`

### Extracção de fornecedores
- Pipeline com Claude (Anthropic API) lê PDFs de fornecedores via PyMuPDF
- Extrai: nome, categoria, dimensões, materiais/cores, imagens ambiente e técnicas
- Guarda em SQLite com FTS5 para pesquisa rápida
- Fornecedores processados até agora:

| Fornecedor | Produtos | Imagens |
|---|---|---|
| Aço Mobilia 2025-7 | 39 | foto ambiente + técnica |
| ACQUARELLA - AGO 2023 | 57 | foto ambiente |
| **Total** | **96** | ✅ |

---

## Estrutura do projecto

```
csm-catalog-extractor/
├── webapp/
│   ├── app.py              # Flask app principal (rotas, auth, watermark, PDF export)
│   ├── loader.py           # SQLite + FTS5, ingestão de JSONs, busca inteligente
│   ├── config.py           # Credenciais e paths
│   ├── pdf_export.py       # Gerador de PDF (fpdf2) — capa + 2 págs/produto
│   ├── static/
│   │   ├── logo.png                # Logo CSM fundo branco
│   │   └── logo-transparent.png   # Logo CSM fundo transparente
│   └── templates/
│       ├── base.html       # Layout base — navbar, footer, tema light/dark, spotlight
│       ├── catalog.html    # Grid de produtos, busca, paginação, modo selecção + exportar PDF
│       ├── login.html      # Página de login
│       ├── product.html    # Detalhe do produto — galeria, lupa zoom, lightbox, specs
│       └── review.html     # Admin — revisão de fornecedores
├── scripts/
│   ├── renderizar_pdfs.py        # Renderiza PDFs em PNG para preview
│   ├── extract_abv.py            # Extracção específica
│   └── fix_aco_mobilia_images.py # Correcção de imagens Aço Mobilia
├── src/extractor/          # Pipeline de extracção com IA (Claude API)
├── data/                   # Local apenas — não vai para o GitHub
│   ├── preview/            # PNGs renderizados
│   ├── output/             # JSONs extraídos por produto
│   ├── watermarked/        # Cache de imagens com marca d'água
│   └── catalog.db          # Base de dados SQLite
├── Abrir Catalogo.bat      # Atalho para iniciar o servidor Flask
├── pyproject.toml
└── .gitignore
```

---

## Instalar num PC novo

```powershell
# 1. Clonar
git clone https://github.com/catalogoscsm-dev/catalogo_csm.git
cd catalogo_csm

# 2. Criar ambiente virtual
python -m venv .venv
.venv\Scripts\activate

# 3. Instalar dependências
pip install -e .

# 4. Configurar credenciais
copy .env.example .env
# Editar o .env com senhas e chave de API

# 5. Abrir o catálogo
"Abrir Catalogo.bat"
# ou: .venv\Scripts\python.exe webapp\app.py
# Aceder em http://localhost:5000
```

**Credenciais padrão** (definidas em `config.py`):
- Admin: `admin` / senha configurada no `.env`
- Cliente: `cliente` / senha configurada no `.env`

---

## Configuração do `.env`

```
ANTHROPIC_API_KEY=sk-ant-...   # Chave Claude (extracção de PDFs)
ADMIN_PASSWORD=...              # Senha do admin
CLIENT_PASSWORD=...             # Senha do cliente
SECRET_KEY=...                  # Chave Flask (string aleatória)
```

---

## Próximos passos

- [ ] Extrair os restantes fornecedores (~119 PDFs)
- [ ] Navegação prev/next entre produtos no detalhe
- [ ] Hospedagem online (Railway/Render + Cloudflare R2 para imagens)
- [ ] Exportação PDF para clientes (versão simplificada sem specs internas)

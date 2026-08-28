# CSM Decor — Catálogo Digital

Catálogo digital de produtos de mobiliário para a CSM Decor.
Site estático gerado a partir de 121 PDFs de fornecedores, publicado no GitHub Pages.

---

## Plano de trabalho

### Divisão de tarefas

**Joao Miguel faz:**
- Dividir os PDFs página a página e identificar a página principal de cada produto
- Selecionar e editar as fotos no Google Gemini (remover preços, textos feios, melhorar qualidade)
- Entregar as imagens organizadas por produto

**Claude faz:**
- Ler os PDFs e extrair nome, dimensões, materiais e categorias de cada produto
- Organizar tudo por nome e palavras-chave
- Cruzar as imagens entregues com as informações extraídas
- Gerar o site HTML estático pronto para publicar no GitHub Pages

---

### Fluxo completo

```
PDFs (121 ficheiros)
  ↓
Claude lê e extrai informações (nome, dimensões, materiais, categoria)
  ↓
Joao Miguel divide páginas + edita fotos no Gemini
  ↓
Claude cruza imagem + info de cada produto
  ↓
Script gera site HTML estático
  ↓
Push para GitHub → publicado em GitHub Pages (grátis, para sempre)
```

---

### Estado actual

| Fornecedor | Produtos | Imagens | Info extraída |
|---|---|---|---|
| Aço Mobilia 2025-7 | 39 | ✅ foto ambiente + técnica | ✅ |
| ACQUARELLA - AGO 2023 | 57 | ✅ só foto ambiente | ✅ |
| Restantes 119 PDFs | — | ⏳ a tratar | ⏳ |

**Total actual: 96 produtos no catálogo**

---

## Site (GitHub Pages)

URL: `https://catalogoscsm-dev.github.io/catalogo_csm`

- Site estático — sem servidor, sem mensalidade
- Pesquisa por JavaScript (nome, categoria, material)
- Vendedores partilham o link directamente com clientes
- Actualizado com um script sempre que entram novos produtos

---

## Estrutura do projecto

```
csm-catalog-extractor/
├── webapp/               # App Flask local (gestão e admin)
│   ├── app.py
│   ├── loader.py
│   ├── config.py
│   └── templates/
├── scripts/
│   ├── renderizar_pdfs.py   # Renderiza PDFs em PNG para preview
│   └── gerar_site.py        # (a criar) Gera o HTML estático
├── src/extractor/           # Pipeline de extracção com IA
├── data/                    # Local apenas — não vai para o GitHub
│   ├── preview/             # PNGs renderizados (10 GB, local)
│   ├── output/              # JSONs extraídos (local)
│   └── catalog.db           # Base de dados SQLite (local)
├── site/                    # (a criar) HTML estático gerado
├── .env.example
└── .gitignore
```

---

## Instalar no PC novo

```powershell
# 1. Clonar o projecto
git clone https://github.com/catalogoscsm-dev/catalogo_csm.git
cd catalogo_csm

# 2. Criar ambiente virtual
python -m venv .venv
.venv\Scripts\activate

# 3. Instalar dependências
pip install -e .

# 4. Configurar credenciais
copy .env.example .env
# Editar o .env com as senhas e chave de API

# 5. Colocar os PDFs em data/pdfs/ e renderizar
python scripts/renderizar_pdfs.py

# 6. Abrir o catálogo local
python webapp/app.py
# Aceder em http://localhost:5000
```

---

## Configuração do .env

```
ANTHROPIC_API_KEY=sk-ant-...   # Chave Claude (extracção de informações)
ADMIN_PASSWORD=...              # Senha do admin no catálogo local
CLIENT_PASSWORD=...             # Senha do cliente no catálogo local
SECRET_KEY=...                  # Chave Flask (qualquer string aleatória)
```

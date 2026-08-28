from __future__ import annotations
import sqlite3
import json
from pathlib import Path

from config import DATA_OUTPUT_DIR, DB_PATH, DATA_DIR


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = get_db()
    conn.executescript("""
        -- Adiciona coluna imagens se ainda não existir (migracao)
        -- SQLite nao suporta IF NOT EXISTS em ALTER TABLE, entao ignoramos erro via executescript
    """)
    try:
        conn.execute("ALTER TABLE products ADD COLUMN imagens TEXT NOT NULL DEFAULT '[]'")
        conn.commit()
    except Exception:
        pass  # coluna ja existe
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS products (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            nome          TEXT NOT NULL DEFAULT '',
            categoria     TEXT NOT NULL DEFAULT '',
            descricao     TEXT NOT NULL DEFAULT '',
            dimensoes     TEXT NOT NULL DEFAULT '',
            materiais     TEXT NOT NULL DEFAULT '[]',
            cores         TEXT NOT NULL DEFAULT '[]',
            paleta_hex    TEXT NOT NULL DEFAULT '[]',
            imagem_path   TEXT NOT NULL DEFAULT '',
            imagens       TEXT NOT NULL DEFAULT '[]',
            pagina_origem INTEGER NOT NULL DEFAULT 0,
            pdf_origem    TEXT NOT NULL DEFAULT '',
            fornecedor    TEXT NOT NULL DEFAULT '',
            aprovado      INTEGER NOT NULL DEFAULT 1
        );

        CREATE VIRTUAL TABLE IF NOT EXISTS products_fts USING fts5(
            nome, categoria, descricao,
            content='products', content_rowid='id'
        );

        CREATE TABLE IF NOT EXISTS ingestion_log (
            pdf_name    TEXT PRIMARY KEY,
            ingested_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            total       INTEGER
        );

        CREATE TABLE IF NOT EXISTS supplier_config (
            fornecedor             TEXT PRIMARY KEY,
            incluir_imagem_tecnica INTEGER NOT NULL DEFAULT 1,
            updated_at             DATETIME DEFAULT CURRENT_TIMESTAMP
        );
    """)
    conn.commit()
    conn.close()


def ingest_all_jsons(force: bool = False) -> int:
    """
    Varre data/output/ e importa resultado_*.json para o SQLite.
    Idempotente — pula PDFs já importados, a menos que force=True.
    Retorna total de produtos importados nesta chamada.
    """
    if not DATA_OUTPUT_DIR.exists():
        return 0

    conn = get_db()
    already_done: set[str] = {
        r["pdf_name"]
        for r in conn.execute("SELECT pdf_name FROM ingestion_log").fetchall()
    }
    conn.close()

    imported = 0

    for pdf_dir in sorted(DATA_OUTPUT_DIR.iterdir()):
        if not pdf_dir.is_dir():
            continue
        pdf_name = pdf_dir.name
        if pdf_name in already_done and not force:
            continue

        jsons = sorted(pdf_dir.glob("resultado_*.json"), reverse=True)
        if not jsons:
            continue

        with open(jsons[0], encoding="utf-8") as f:
            data = json.load(f)

        produtos = data.get("produtos", [])
        fornecedor_pdf = data.get("fornecedor", pdf_name)
        configs = get_supplier_configs()
        incluir_tec = configs.get(fornecedor_pdf, True)

        conn = get_db()

        # Remove entradas antigas deste PDF (suporte a re-ingestão)
        conn.execute("DELETE FROM products WHERE pdf_origem = ?", (data.get("pdf_path", pdf_name),))

        for p in produtos:
            imagem_path = (p.get("imagem_path") or "").replace("\\", "/")
            imagens_raw = p.get("imagens", [])
            if not incluir_tec:
                imagens_raw = [i for i in imagens_raw if "_tec" not in i.lower()]
            imagens = json.dumps(
                [i.replace("\\", "/") for i in imagens_raw],
                ensure_ascii=False,
            )
            conn.execute(
                """
                INSERT INTO products
                    (nome, categoria, descricao, dimensoes, materiais, cores,
                     paleta_hex, imagem_path, imagens, pagina_origem, pdf_origem, fornecedor, aprovado)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
                """,
                (
                    p.get("nome", ""),
                    p.get("categoria", ""),
                    p.get("descricao", ""),
                    p.get("dimensoes", ""),
                    json.dumps(p.get("materiais", []), ensure_ascii=False),
                    json.dumps(p.get("cores_disponiveis", []), ensure_ascii=False),
                    json.dumps(p.get("paleta_hex", []), ensure_ascii=False),
                    imagem_path,
                    imagens,
                    p.get("pagina_origem", 0),
                    data.get("pdf_path", pdf_name),
                    p.get("fornecedor_interno") or data.get("fornecedor", ""),
                ),
            )

        conn.execute(
            "INSERT OR REPLACE INTO ingestion_log (pdf_name, total) VALUES (?, ?)",
            (pdf_name, len(produtos)),
        )
        conn.commit()

        # Recria índice FTS após cada PDF
        conn.execute("INSERT INTO products_fts(products_fts) VALUES('rebuild')")
        conn.commit()
        conn.close()

        imported += len(produtos)
        print(f"[loader] {pdf_name}: {len(produtos)} produto(s) importado(s)")

    return imported


def search_products(
    q: str = "",
    categoria: str = "",
    page: int = 1,
    per_page: int = 24,
) -> tuple[list[sqlite3.Row], int]:
    """Retorna (produtos, total) para a query e página dadas."""
    conn = get_db()
    params: list = []

    if q:
        ids = [
            r[0]
            for r in conn.execute(
                "SELECT rowid FROM products_fts WHERE products_fts MATCH ? ORDER BY rank",
                (q,),
            ).fetchall()
        ]
        if not ids:
            conn.close()
            return [], 0

        placeholders = ",".join("?" * len(ids))
        where = f"id IN ({placeholders}) AND aprovado = 1"
        params = list(ids)
    else:
        where = "aprovado = 1"

    if categoria:
        where += " AND categoria = ?"
        params.append(categoria)

    total: int = conn.execute(
        f"SELECT COUNT(*) FROM products WHERE {where}", params
    ).fetchone()[0]

    rows = conn.execute(
        f"SELECT * FROM products WHERE {where} ORDER BY id DESC LIMIT ? OFFSET ?",
        params + [per_page, (page - 1) * per_page],
    ).fetchall()

    conn.close()
    return rows, total


def get_supplier_configs() -> dict[str, bool]:
    conn = get_db()
    rows = conn.execute("SELECT fornecedor, incluir_imagem_tecnica FROM supplier_config").fetchall()
    conn.close()
    return {r["fornecedor"]: bool(r["incluir_imagem_tecnica"]) for r in rows}


def set_supplier_config(fornecedor: str, incluir_imagem_tecnica: bool) -> None:
    conn = get_db()
    conn.execute(
        """INSERT OR REPLACE INTO supplier_config (fornecedor, incluir_imagem_tecnica, updated_at)
           VALUES (?, ?, CURRENT_TIMESTAMP)""",
        (fornecedor, int(incluir_imagem_tecnica)),
    )
    conn.commit()
    conn.close()


def get_preview_suppliers() -> list[dict]:
    """
    Lista todos os fornecedores com PNGs renderizados em data/preview/.
    Retorna dicts com nome, páginas disponíveis e config actual.
    """
    preview_dir = DATA_DIR / "preview"
    if not preview_dir.exists():
        return []

    configs = get_supplier_configs()
    suppliers = []

    for folder in sorted(preview_dir.iterdir()):
        if not folder.is_dir():
            continue
        pngs = sorted(folder.glob("pag*.png"))
        if not pngs:
            continue
        nome = folder.name
        suppliers.append({
            "nome": nome,
            "total_paginas": len(pngs),
            "paginas": [f"preview/{nome}/{p.name}" for p in pngs[:6]],
            "incluir_imagem_tecnica": configs.get(nome, True),
        })

    return suppliers


def get_categorias() -> list[str]:
    conn = get_db()
    rows = conn.execute(
        "SELECT DISTINCT categoria FROM products WHERE aprovado = 1 AND categoria != '' ORDER BY categoria"
    ).fetchall()
    conn.close()
    return [r[0] for r in rows]

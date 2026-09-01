from __future__ import annotations
import hashlib
import io
import json as json_module
import re as re_module
from functools import wraps
from pathlib import Path

from flask import (
    Flask,
    render_template,
    request,
    session,
    redirect,
    url_for,
    send_from_directory,
    jsonify,
    Response,
)

import sys
sys.path.insert(0, str(Path(__file__).parent))

from config import SECRET_KEY, USERS, DATA_DIR
from loader import (
    init_db, ingest_all_jsons, search_products, get_categorias,
    get_preview_suppliers, set_supplier_config,
)

app = Flask(__name__)
app.secret_key = SECRET_KEY

LOGO_PATH = Path(__file__).parent / "static" / "logo.png"
# Em produção o repo pode ser read-only; usa /tmp como fallback
_wm_primary = DATA_DIR / "watermarked"
try:
    _wm_primary.mkdir(exist_ok=True)
    WM_CACHE = _wm_primary
except OSError:
    import tempfile
    WM_CACHE = Path(tempfile.gettempdir()) / "csm_wm_cache"
    WM_CACHE.mkdir(exist_ok=True)


def _apply_watermark(img_path: Path) -> bytes:
    """Sobrepõe o logo CSM como marca d'água no canto inferior direito."""
    from PIL import Image

    img  = Image.open(img_path).convert("RGBA")
    iw, ih = img.size

    logo = Image.open(LOGO_PATH).convert("RGBA")

    # Torna pixels brancos/quase-brancos transparentes
    data = logo.getdata()
    new_data = []
    for r, g, b, a in data:
        if r > 220 and g > 220 and b > 220:
            new_data.append((r, g, b, 0))
        else:
            new_data.append((r, g, b, int(a * 0.28)))   # 28% opacidade
    logo.putdata(new_data)

    # Redimensiona logo para 22% da largura da imagem
    lw = max(80, int(iw * 0.22))
    lh = int(logo.height * lw / logo.width)
    logo = logo.resize((lw, lh), Image.LANCZOS)

    # Posição: canto inferior direito com margem de 1.5%
    pad = max(8, int(iw * 0.015))
    pos = (iw - lw - pad, ih - lh - pad)

    img.paste(logo, pos, logo)

    buf = io.BytesIO()
    img.convert("RGB").save(buf, "JPEG", quality=92)
    return buf.getvalue()


def _serve_watermarked(subpath: str):
    """Retorna a imagem com marca d'água, usando cache em disco."""
    img_path = DATA_DIR / subpath
    if not img_path.exists():
        return send_from_directory(str(DATA_DIR), subpath)

    cache_key  = hashlib.md5(subpath.encode()).hexdigest() + ".jpg"
    cache_path = WM_CACHE / cache_key

    if not cache_path.exists():
        try:
            cache_path.write_bytes(_apply_watermark(img_path))
        except Exception:
            return send_from_directory(str(DATA_DIR), subpath)

    return send_from_directory(str(WM_CACHE), cache_key)


@app.template_filter("fromjson")
def fromjson_filter(s):
    try:
        return json_module.loads(s) if isinstance(s, str) else (s or [])
    except Exception:
        return []


@app.template_filter("parse_dims")
def parse_dims_filter(dim_str: str) -> list[dict]:
    """
    Formato retangular: 'P - 115cm x 45cm x h.70cm'
    → [{'size':'P','largura':'115cm','prof':'45cm','altura':'70cm','circular':False}, ...]

    Formato circular: 'P - Ø40cm x h.45cm'
    → [{'size':'P','diametro':'40cm','altura':'45cm','circular':True}, ...]
    """
    if not dim_str:
        return []
    rows = []
    for part in dim_str.split("|"):
        part = part.strip()
        m = re_module.match(r'^([A-Z][A-Z0-9]*(?:\s+[A-Z][A-Z0-9]*)*)\s*[-–]\s*(.+)', part)
        if not m:
            continue
        size  = m.group(1)
        resto = m.group(2).strip()

        # Formato circular: começa com Ø ou ø
        circ = re_module.match(r'^[Øø](\S+)\s+x\s+h\.?(\S+)', resto, re_module.IGNORECASE)
        if circ:
            rows.append({"size": size, "diametro": circ.group(1), "altura": circ.group(2), "circular": True})
            continue

        # Formato retangular
        resto = re_module.sub(r'x\s*h\.', 'x h.', resto)
        segments = [s.strip() for s in re_module.split(r'\s+x\s+', resto)]
        row: dict = {"size": size, "circular": False}
        keys = ["largura", "prof", "altura"]
        for i, seg in enumerate(segments):
            val = re_module.sub(r'^h\.', '', seg).strip()
            if i < len(keys):
                row[keys[i]] = val
        rows.append(row)
    return rows


# ── Inicialização ────────────────────────────────────────────────────────────

with app.app_context():
    init_db()
    # Pré-configura fornecedores já conhecidos
    set_supplier_config("Aço Mobilia 2025-7", True)   # inclui imagem técnica
    set_supplier_config("ACQUARELLA - AGO 2023", False)  # só foto ambiente
    imported = ingest_all_jsons()
    if imported:
        print(f"[app] {imported} produto(s) importado(s) na inicialização")


# ── Decoradores de autenticação ──────────────────────────────────────────────

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if session.get("role") != "admin":
            return redirect(url_for("catalog"))
        return f(*args, **kwargs)
    return decorated


# ── Autenticação ─────────────────────────────────────────────────────────────

@app.route("/admin/login", methods=["POST"])
def admin_login():
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")
    user = USERS.get(username)
    if user and user["password"] == password and user["role"] == "admin":
        session["user"] = username
        session["role"] = "admin"
        return redirect(url_for("catalog"))
    return redirect(url_for("catalog", admin_error=1))


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("catalog"))


# ── Catálogo ─────────────────────────────────────────────────────────────────

@app.route("/")
def catalog():
    q         = request.args.get("q", "").strip()
    categoria = request.args.get("categoria", "").strip()
    page      = max(1, int(request.args.get("page", 1)))
    is_admin  = session.get("role") == "admin"

    products, total = search_products(q=q, categoria=categoria, page=page, per_page=24)
    categorias      = get_categorias()

    return render_template(
        "catalog.html",
        products=products,
        q=q, categoria=categoria, categorias=categorias,
        page=page, per_page=24, total=total, is_admin=is_admin,
    )


# ── Detalhe do produto ────────────────────────────────────────────────────────

@app.route("/produto/<int:pid>")
def product_detail(pid):
    from loader import get_db, search_products
    is_admin = session.get("role") == "admin"
    q         = request.args.get("q", "").strip()
    categoria = request.args.get("categoria", "").strip()

    conn = get_db()
    product = conn.execute("SELECT * FROM products WHERE id = ?", (pid,)).fetchone()
    conn.close()
    if not product:
        return "Produto não encontrado.", 404

    # Descobre prev/next dentro do contexto de busca atual
    all_products, _ = search_products(q=q, categoria=categoria, page=1, per_page=9999)
    ids = [p["id"] for p in all_products]
    prev_id = next_id = None
    if pid in ids:
        idx = ids.index(pid)
        if idx > 0:
            prev_id = ids[idx - 1]
        if idx < len(ids) - 1:
            next_id = ids[idx + 1]

    return render_template(
        "product.html",
        product=product,
        is_admin=is_admin,
        prev_id=prev_id,
        next_id=next_id,
        q=q,
        categoria=categoria,
    )


# ── Servir imagens com marca d'água ──────────────────────────────────────────

@app.route("/imagem/<path:subpath>")
def serve_image(subpath):
    return _serve_watermarked(subpath)


# ── Admin: re-ingestão ────────────────────────────────────────────────────────

@app.route("/admin/reingest")
@admin_required
def reingest():
    n = ingest_all_jsons(force=False)
    return redirect(url_for("catalog", _anchor=f"reingest:{n}"))


# ── Admin: revisão de fornecedores ────────────────────────────────────────────

@app.route("/admin/review")
@admin_required
def review():
    suppliers = get_preview_suppliers()
    return render_template("review.html", suppliers=suppliers)


@app.route("/admin/api/supplier-config", methods=["POST"])
@admin_required
def api_supplier_config():
    data = request.get_json(force=True)
    fornecedor = data.get("fornecedor", "").strip()
    incluir = bool(data.get("incluir_imagem_tecnica", True))
    if not fornecedor:
        return jsonify({"ok": False, "erro": "fornecedor em falta"}), 400
    set_supplier_config(fornecedor, incluir)
    return jsonify({"ok": True, "fornecedor": fornecedor, "incluir_imagem_tecnica": incluir})


# ── Exportar PDF ─────────────────────────────────────────────────────────────

@app.route("/exportar-pdf", methods=["POST"])
def exportar_pdf():
    from loader import get_db
    from pdf_export import build_pdf

    ids_raw = request.form.get("ids", "")
    try:
        ids = [int(i) for i in ids_raw.split(",") if i.strip().isdigit()]
    except ValueError:
        return "IDs inválidos.", 400

    if not ids or len(ids) > 100:
        return "Selecione entre 1 e 100 produtos.", 400

    conn = get_db()
    placeholders = ",".join("?" * len(ids))
    rows = conn.execute(
        f"SELECT * FROM products WHERE id IN ({placeholders}) AND aprovado = 1",
        ids,
    ).fetchall()
    conn.close()

    products = [dict(r) for r in rows]
    if not products:
        # IDs não existem no banco (ex: localStorage com IDs antigos após reconstrução do banco)
        return (
            "<h2>Nenhum produto encontrado.</h2>"
            "<p>Os produtos selecionados já não existem. "
            "Por favor limpe a seleção no browser e selecione novamente.</p>"
            "<p><b>No browser: F12 → Console → "
            "<code>localStorage.removeItem('csm_selected_ids')</code> → F5</b></p>",
            400,
        )

    # Mantém a ordem de seleção do usuário
    order = {pid: i for i, pid in enumerate(ids)}
    products.sort(key=lambda p: order.get(p["id"], 999))

    try:
        pdf_bytes = build_pdf(products)
    except Exception as exc:
        app.logger.error("Erro ao gerar PDF: %s", exc, exc_info=True)
        return f"Erro ao gerar PDF: {exc}", 500

    from datetime import datetime
    filename = f"CSM_Decor_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"

    return Response(
        pdf_bytes,
        mimetype="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)

from __future__ import annotations
import json as json_module
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


@app.template_filter("fromjson")
def fromjson_filter(s):
    try:
        return json_module.loads(s) if isinstance(s, str) else (s or [])
    except Exception:
        return []


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

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user" not in session or session.get("role") != "admin":
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


# ── Autenticação ─────────────────────────────────────────────────────────────

@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = USERS.get(username)
        if user and user["password"] == password:
            session["user"] = username
            session["role"] = user["role"]
            return redirect(url_for("catalog"))
        error = "Usuário ou senha inválidos."
    return render_template("login.html", error=error)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ── Catálogo ─────────────────────────────────────────────────────────────────

@app.route("/")
@login_required
def catalog():
    q         = request.args.get("q", "").strip()
    categoria = request.args.get("categoria", "").strip()
    page      = max(1, int(request.args.get("page", 1)))
    is_admin  = session.get("role") == "admin"

    products, total = search_products(q=q, categoria=categoria, page=page)
    categorias      = get_categorias()

    return render_template(
        "catalog.html",
        products=products,
        q=q,
        categoria=categoria,
        categorias=categorias,
        page=page,
        per_page=24,
        total=total,
        is_admin=is_admin,
    )


# ── Detalhe do produto ────────────────────────────────────────────────────────

@app.route("/produto/<int:pid>")
@login_required
def product_detail(pid):
    from loader import get_db
    is_admin = session.get("role") == "admin"
    conn = get_db()
    product = conn.execute("SELECT * FROM products WHERE id = ?", (pid,)).fetchone()
    conn.close()
    if not product:
        return "Produto não encontrado.", 404
    return render_template("product.html", product=product, is_admin=is_admin)


# ── Servir imagens (autenticado) ──────────────────────────────────────────────

@app.route("/imagem/<path:subpath>")
@login_required
def serve_image(subpath):
    return send_from_directory(str(DATA_DIR), subpath)


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


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)

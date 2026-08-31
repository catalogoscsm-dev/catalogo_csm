"""
Gerador de PDF para o catálogo CSM Decor.

Layout por produto (A4 portrait):
  ┌─────────────────────────────────────────────────┐
  │ linha dourada                                   │
  │ CATEGORIA                              CSM DECOR│
  │ Nome do Produto                                 │
  │ ── linha dourada ──────────────────────────────  │
  │                                                 │
  │  [  Imagem 1 (amb)  ]  DIMENSÕES                │
  │  [                  ]  P | 115cm | 45cm | 70cm  │
  │  [                  ]  G | 155cm | 45cm | 70cm  │
  │                        ─────────────────────    │
  │  [  Imagem 2 (tec)  ]  ACABAMENTOS              │
  │  [                  ]  • Branco Neve            │
  │  [                  ]  • Grafite                │
  │                                                 │
  │ linha dourada                        Página N   │
  └─────────────────────────────────────────────────┘

Funciona com 0, 1 ou 2 imagens — adapta o espaço automaticamente.
"""
from __future__ import annotations
import json
import math
import re
from datetime import datetime
from pathlib import Path

from fpdf import FPDF

from config import DATA_DIR

# ── Fontes ────────────────────────────────────────────────────────────────────
_FONTS = Path(r"C:\Windows\Fonts")
_F_REG  = str(_FONTS / "arial.ttf")
_F_BOLD = str(_FONTS / "arialbd.ttf")
_F_ITAL = str(_FONTS / "ariali.ttf")

LOGO_PATH = Path(__file__).parent / "static" / "logo.png"

# ── Mapa de cores de acabamento ───────────────────────────────────────────────
_COR_MAP: dict[str, tuple[int,int,int]] = {
    # brancos / claros
    "branco":            (255, 255, 255),
    "branco neve":       (250, 250, 248),
    "branco fosco":      (240, 240, 238),
    "off white":         (242, 237, 224),
    "offwhite":          (242, 237, 224),
    "creme":             (238, 228, 205),
    "champagne":         (240, 222, 179),
    "palha":             (220, 200, 140),
    "areia":             (210, 192, 155),
    "linho":             (218, 208, 185),
    "marfim":            (236, 228, 202),
    "bege":              (218, 200, 168),
    # cinzas
    "cinza":             (160, 160, 160),
    "cinza claro":       (200, 200, 200),
    "cinza médio":       (130, 130, 130),
    "grafite":           ( 80,  80,  80),
    "chumbo":            ( 65,  70,  78),
    "antracite":         ( 55,  58,  62),
    # pretos
    "preto":             ( 25,  25,  25),
    "preto fosco":       ( 35,  35,  35),
    "preto brilhante":   ( 10,  10,  10),
    # madeiras claras
    "natural":           (196, 160, 105),
    "mel":               (200, 148,  58),
    "pinho":             (210, 175, 115),
    "freijó":            (182, 142,  88),
    "freijo":            (182, 142,  88),
    "amendoa":           (190, 152, 100),
    "amêndoa":           (190, 152, 100),
    "carvalho":          (162, 122,  72),
    "carvalho americano":(158, 118,  68),
    "carvalho claro":    (185, 148,  95),
    "carvalho europeu":  (148, 108,  62),
    "eucalipto":         (175, 145,  95),
    "pé de galinha":     (172, 138,  85),
    # madeiras médias
    "capuccino":         (155, 108,  72),
    "cappuccino":        (155, 108,  72),
    "tabaco":            (118,  78,  45),
    "castanho":          (125,  85,  48),
    "noz":               (108,  72,  38),
    "noce":              (108,  72,  38),
    "canela":            (140,  90,  48),
    "imbuia":            ( 95,  62,  32),
    "mogno":             (120,  50,  28),
    # madeiras escuras
    "cacau":             ( 92,  52,  28),
    "chocolate":         ( 78,  42,  20),
    "marrom":            ( 98,  58,  28),
    "terra":             (112,  72,  38),
    "wengue":            ( 42,  22,  12),
    "wenge":             ( 42,  22,  12),
    "ebano":             ( 28,  18,  10),
    "ébano":             ( 28,  18,  10),
    # cores vivas
    "vermelho":          (192,  40,  40),
    "bordô":             (120,  20,  30),
    "bordo":             (120,  20,  30),
    "rosa":              (220, 140, 150),
    "salmão":            (220, 140, 110),
    "laranja":           (220, 100,  30),
    "amarelo":           (220, 195,  50),
    "verde":             ( 60, 140,  70),
    "verde militar":     ( 58,  90,  55),
    "azul":              ( 45,  95, 170),
    "azul marinho":      ( 20,  40,  90),
    "azul petróleo":     ( 25,  80,  95),
    "petróleo":          ( 25,  80,  95),
    "turquesa":          ( 45, 155, 155),
    "roxo":              (100,  50, 140),
    "lilás":             (170, 130, 200),
    "cobre":             (180, 100,  50),
    "dourado":           (200, 165,  60),
    "gold":              (200, 165,  60),
    "prata":             (185, 185, 188),
    "cromado":           (195, 195, 200),
}

def _cor_rgb(nome: str) -> tuple[int,int,int]:
    """Retorna RGB aproximado para um nome de cor/acabamento."""
    key = nome.lower().strip()
    if key in _COR_MAP:
        return _COR_MAP[key]
    # tenta correspondência parcial (ex: "Branco Snow" → "branco")
    for k, v in _COR_MAP.items():
        if k in key or key in k:
            return v
    return (140, 135, 128)   # cinza neutro para cores desconhecidas

# ── Paleta CSM ────────────────────────────────────────────────────────────────
GOLD   = (255, 125,   0)   # laranja CSM #FF7D00
GOLD_L = (255, 212, 168)   # laranja claro
CREAM  = (250, 250, 248)
CREAM2 = (255, 245, 236)
INK    = (26,  26,  26)
SOFT   = (61,  61,  61)
MUTED  = (107, 107, 107)
FAINT  = (176, 168, 152)
WHITE  = (255, 255, 255)

# ── Dimensões A4 ──────────────────────────────────────────────────────────────
PW, PH = 210, 297
MX, MY = 13, 13          # margens esquerda/topo/direita/base
CW = PW - 2 * MX         # largura útil = 184mm

IMG_COL  = 104            # largura coluna de imagens
SPEC_COL = CW - IMG_COL - 6  # largura coluna de specs (~74mm)
SPEC_X   = MX + IMG_COL + 6  # x inicial da coluna de specs

HEADER_H = 26             # altura do bloco de cabeçalho
FOOTER_H = 10             # altura do rodapé
BODY_Y   = MY + HEADER_H  # onde começa o corpo
BODY_H   = PH - MY - HEADER_H - FOOTER_H  # altura disponível para imagens+specs


# ─────────────────────────────────────────────────────────────────────────────

def _parse_dims(dim_str: str) -> list[dict]:
    """Converte 'P - 115cm x 45cm x h.70cm | G - ...' em lista de dicts."""
    rows = []
    for part in dim_str.split("|"):
        part = part.strip()
        m = re.match(r'^([A-Z]+)\s*[-–]\s*(.+)', part)
        if not m:
            continue
        size  = m.group(1)
        resto = re.sub(r'x\s*h\.', 'x h.', m.group(2).strip())
        segs  = [s.strip().lstrip("h.") for s in re.split(r'\s+x\s+', resto)]
        while len(segs) < 3:
            segs.append("—")
        rows.append({"size": size, "l": segs[0], "p": segs[1], "a": segs[2]})
    return rows


def _load_json_field(val) -> list:
    if isinstance(val, str):
        try:
            return json.loads(val) or []
        except Exception:
            return []
    return val or []


# ─────────────────────────────────────────────────────────────────────────────

class CatalogPDF(FPDF):

    def __init__(self):
        super().__init__(orientation="P", unit="mm", format="A4")
        self.add_font("Arial", style="",  fname=_F_REG)
        self.add_font("Arial", style="B", fname=_F_BOLD)
        self.add_font("Arial", style="I", fname=_F_ITAL)
        self.set_margins(MX, MY, MX)
        self.set_auto_page_break(auto=False)

    # ── helpers ───────────────────────────────────────────────────────────────

    def _gold_line(self, x: float, y: float, w: float, t: float = 0.4):
        self.set_draw_color(*GOLD)
        self.set_line_width(t)
        self.line(x, y, x + w, y)
        self.set_line_width(0.2)
        self.set_draw_color(*GOLD_L)

    def _place_image(self, path: Path, x: float, y: float,
                     max_w: float, max_h: float) -> float:
        """
        Insere imagem com marca d'água preservando proporção dentro de max_w × max_h.
        Retorna a altura real ocupada.
        """
        if not path.exists():
            return 0
        try:
            from PIL import Image as PILImage, ImageDraw
            import io as _io

            with PILImage.open(path) as im:
                iw, ih = im.size
                img = im.convert("RGBA")

            # Aplica marca d'água se logo disponível
            if LOGO_PATH.exists():
                logo = PILImage.open(LOGO_PATH).convert("RGBA")
                data = logo.getdata()
                new_data = []
                for r, g, b, a in data:
                    alpha = 0 if (r > 220 and g > 220 and b > 220) else int(a * 0.22)
                    new_data.append((r, g, b, alpha))
                logo.putdata(new_data)
                lw = max(60, int(iw * 0.20))
                lh = int(logo.height * lw / logo.width)
                logo = logo.resize((lw, lh), PILImage.LANCZOS)
                pad = max(6, int(iw * 0.015))
                img.paste(logo, (iw - lw - pad, ih - lh - pad), logo)

            buf = _io.BytesIO()
            img.convert("RGB").save(buf, "JPEG", quality=90)
            buf.seek(0)

        except Exception:
            iw, ih = int(max_w * 10), int(max_h * 10)
            buf = None

        ratio = min(max_w / iw, max_h / ih)
        dw = iw * ratio
        dh = ih * ratio
        ox = x + (max_w - dw) / 2

        if buf:
            self.image(buf, x=ox, y=y, w=dw, h=dh)
        else:
            self.image(str(path), x=ox, y=y, w=dw, h=dh)

        self.set_draw_color(*GOLD_L)
        self.set_line_width(0.25)
        self.rect(ox, y, dw, dh)
        return dh

    # ── capa ──────────────────────────────────────────────────────────────────

    def cover_page(self, total: int, subtitle: str = "Seleção de Produtos"):
        self.add_page()

        # fundo cream
        self.set_fill_color(*CREAM)
        self.rect(0, 0, PW, PH, "F")

        # ── Layout com posicionamento absoluto para evitar sobreposição ───────
        # Zona do conteúdo: entre y=85 e y=195
        LINE_TOP  = 88   # linha decorativa superior
        LOGO_Y    = 98   # topo do logo
        LOGO_W    = 62   # largura do logo
        TITLE_Y   = 152  # título (abaixo do logo com margem)
        SUBS_Y    = 166  # subtítulo
        INFO_Y    = 176  # linha de info (qtd + data)
        LINE_BOT  = 187  # linha decorativa inferior

        # Linhas decorativas laranja
        self._gold_line(MX, LINE_TOP, CW, 0.6)
        self._gold_line(MX, LINE_BOT, CW, 0.6)

        # Logo CSM — centrado, com espaço garantido antes do título
        if LOGO_PATH.exists():
            logo_x = (PW - LOGO_W) / 2
            self.image(str(LOGO_PATH), x=logo_x, y=LOGO_Y, w=LOGO_W)
        else:
            self.set_xy(MX, LOGO_Y)
            self.set_font("Arial", "B", 28)
            self.set_text_color(*GOLD)
            self.cell(CW, 14, "CSM", align="C")

        # Título
        self.set_xy(MX, TITLE_Y)
        self.set_font("Arial", "B", 20)
        self.set_text_color(*INK)
        self.cell(CW, 10, "Catálogo de Produtos", align="C")

        # Subtítulo
        self.set_xy(MX, SUBS_Y)
        self.set_font("Arial", "I", 10)
        self.set_text_color(*MUTED)
        self.cell(CW, 6, subtitle, align="C")

        # Info: quantidade + data
        self.set_xy(MX, INFO_Y)
        self.set_font("Arial", "", 8.5)
        self.set_text_color(*FAINT)
        n = f"{total} produto{'s' if total != 1 else ''}"
        data = datetime.now().strftime("%d/%m/%Y")
        self.cell(CW, 5, f"{n}  ·  {data}", align="C")

        # Rodapé
        self.set_xy(MX, PH - MY - 6)
        self.set_font("Arial", "", 7)
        self.set_text_color(*FAINT)
        self.cell(CW, 5, "Uso exclusivo interno — Campinas Shopping Móveis", align="C")

    # ── cabeçalho padrão de página de produto ────────────────────────────────

    def _product_header(self, nome: str, cat: str):
        """Desenha o cabeçalho comum às duas páginas do produto."""
        self._gold_line(MX, MY, CW, 0.55)

        if LOGO_PATH.exists():
            self.image(str(LOGO_PATH), x=PW - MX - 26, y=MY + 1, w=26)

        self.set_xy(MX, MY + 2)
        self.set_font("Arial", "B", 7)
        self.set_text_color(*GOLD)
        self.cell(CW - 28, 5, cat, align="L")

        self.set_xy(MX, MY + 8)
        self.set_font("Arial", "B", 15)
        self.set_text_color(*INK)
        display = nome if len(nome) <= 44 else nome[:42] + "…"
        self.cell(CW, 8, display, align="L")

        self._gold_line(MX, MY + 17, CW * 0.6, 0.35)

    def _product_footer(self, label: str = ""):
        footer_y = PH - MY - FOOTER_H + 2
        self._gold_line(MX, footer_y, CW, 0.3)
        self.set_xy(MX, footer_y + 2)
        self.set_font("Arial", "", 6.5)
        self.set_text_color(*FAINT)
        self.cell(CW / 2, 4, f"CSM Decor — Uso Exclusivo Interno{('  ·  ' + label) if label else ''}", align="L")
        self.cell(CW / 2, 4, f"Página {self.page_no()}", align="R")

    # ── Página 1: foto principal ──────────────────────────────────────────────

    def _page_main_photo(self, nome: str, cat: str, img_path):
        self.add_page()
        self._product_header(nome, cat)

        body_y  = MY + 22
        body_h  = PH - body_y - FOOTER_H - MY - 4

        if img_path and img_path.exists():
            h = self._place_image(img_path, MX, body_y, CW, body_h)
            if h > 0:
                self.set_xy(MX, body_y + h + 1.5)
                self.set_font("Arial", "I", 6.5)
                self.set_text_color(*FAINT)
                self.cell(CW, 3, "Imagem ilustrativa", align="C")
        else:
            # placeholder elegante
            self.set_fill_color(*CREAM2)
            self.rect(MX, body_y, CW, body_h * 0.7, "F")
            self.set_xy(MX, body_y + body_h * 0.35 - 5)
            self.set_font("Arial", "I", 10)
            self.set_text_color(*FAINT)
            self.cell(CW, 8, "Imagem não disponível", align="C")

        self._product_footer("Foto Principal")

    # ── Página 2: fotos secundárias + specs ──────────────────────────────────

    def _page_specs(self, nome: str, cat: str, secondary_imgs: list,
                    dims: list, cores: list, forn: str):
        self.add_page()
        self._product_header(nome, cat)

        body_y = MY + 22
        body_h = PH - body_y - FOOTER_H - MY - 4

        has_imgs  = len(secondary_imgs) > 0
        has_specs = bool(dims or cores or forn)

        # Divide a página: fotos na metade superior, specs abaixo
        if has_imgs and has_specs:
            img_zone_h  = body_h * 0.63
            specs_y     = body_y + img_zone_h + 14
        elif has_imgs:
            img_zone_h  = body_h * 0.88
            specs_y     = body_y + img_zone_h + 6
        else:
            img_zone_h  = 0
            specs_y     = body_y

        # ── Fotos secundárias ─────────────────────────────────────────────
        if has_imgs:
            n = min(len(secondary_imgs), 3)
            gap = 4
            img_w = (CW - gap * (n - 1)) / n

            for i, rel_path in enumerate(secondary_imgs[:n]):
                p = DATA_DIR / rel_path
                x = MX + i * (img_w + gap)
                h = self._place_image(p, x, body_y, img_w, img_zone_h - 5)
                if h > 0:
                    self.set_xy(x, body_y + h + 1)
                    self.set_font("Arial", "I", 6)
                    self.set_text_color(*FAINT)
                    label = "Vista técnica" if i > 0 else "Vista alternativa"
                    self.cell(img_w, 3, label, align="C")

            # linha separadora
            if has_specs:
                self._gold_line(MX, specs_y - 4, CW, 0.3)

        # ── Specs ─────────────────────────────────────────────────────────
        if has_specs:
            sy = specs_y

            if dims:
                sy = self._draw_section_title_full("DIMENSÕES", sy)
                sy = self._draw_dims_table_full(dims, sy)
                sy += 5

            if cores:
                sy = self._draw_section_title_full("ACABAMENTOS / CORES", sy)
                sy = self._draw_cores_full(cores, sy)
                sy += 5

            if forn:
                sy = self._draw_section_title_full("FORNECEDOR", sy)
                self.set_xy(MX, sy)
                self.set_font("Arial", "", 8)
                self.set_text_color(*MUTED)
                self.multi_cell(CW, 5, forn)

        elif not has_imgs:
            self.set_xy(MX, body_y + 20)
            self.set_font("Arial", "I", 9)
            self.set_text_color(*FAINT)
            self.cell(CW, 8, "Sem especificações técnicas disponíveis", align="C")

        self._product_footer("Especificações Técnicas")

    # ── Entrada pública: 2 páginas por produto ────────────────────────────────

    def product_pages(self, product: dict):
        imgs  = _load_json_field(product.get("imagens", "[]"))
        if not imgs and product.get("imagem_path"):
            imgs = [product["imagem_path"]]

        cores = _load_json_field(product.get("cores", "[]"))
        dims  = _parse_dims(product.get("dimensoes", ""))
        nome  = (product.get("nome") or "Produto").upper()
        cat   = (product.get("categoria") or "").upper()
        forn  = product.get("fornecedor") or ""

        main_img   = DATA_DIR / imgs[0] if imgs else None
        secondary  = imgs[1:] if len(imgs) > 1 else []

        self._page_main_photo(nome, cat, main_img)
        self._page_specs(nome, cat, secondary, dims, cores, forn)

    # ── helpers de specs (largura total da página) ────────────────────────────

    def _draw_section_title_full(self, title: str, y: float) -> float:
        self.set_xy(MX, y)
        self.set_font("Arial", "B", 7.5)
        self.set_text_color(*GOLD)
        self.cell(CW, 5, title, align="L")
        self._gold_line(MX, y + 5, CW * 0.4, 0.25)
        return y + 7.5

    def _draw_dims_table_full(self, dims: list[dict], y: float) -> float:
        col_w = CW / 4
        headers = ["TAMANHO", "LARGURA", "PROFUNDIDADE", "ALTURA"]

        self.set_xy(MX, y)
        self.set_font("Arial", "B", 7)
        self.set_text_color(*FAINT)
        self.set_fill_color(*CREAM2)
        self.set_draw_color(*GOLD_L)
        self.set_line_width(0.2)
        for h in headers:
            self.cell(col_w, 5.5, h, border=1, align="C", fill=True)
        y += 5.5

        self.set_font("Arial", "", 8)
        for i, row in enumerate(dims):
            fill = i % 2 == 0
            self.set_fill_color(248, 243, 235) if fill else self.set_fill_color(*WHITE)
            self.set_xy(MX, y)
            self.set_font("Arial", "B", 8)
            self.set_text_color(*INK)
            self.cell(col_w, 5.5, row["size"], border=1, align="C", fill=fill)
            self.set_font("Arial", "", 8)
            self.set_text_color(*SOFT)
            for val in [row["l"], row["p"], row["a"]]:
                self.cell(col_w, 5.5, val, border=1, align="C", fill=fill)
            y += 5.5

        return y

    def _gradient_circle(self, cx: float, cy: float, r: float,
                         rgb: tuple[int,int,int]):
        """Círculo com gradiente vertical simulado por faixas horizontais."""
        rv, gv, bv = rgb
        # claro no topo (mistura 55% branco)
        rl = int(rv + (255 - rv) * 0.55)
        gl = int(gv + (255 - gv) * 0.55)
        bl = int(bv + (255 - bv) * 0.55)
        # escuro embaixo (70% da cor)
        rd = int(rv * 0.68)
        gd = int(gv * 0.68)
        bd = int(bv * 0.68)

        steps = 40
        for i in range(steps):
            t = i / (steps - 1)                      # 0 → 1 (topo → base)
            dy = -r + t * 2 * r                      # offset do centro
            chord = math.sqrt(max(0, r*r - dy*dy))   # meia-largura da faixa
            if chord < 0.01:
                continue
            strip_y = cy + dy
            strip_h = (2 * r / steps) + 0.15         # +0.15 evita buracos
            cr = int(rl + (rd - rl) * t)
            cg = int(gl + (gd - gl) * t)
            cb = int(bl + (bd - bl) * t)
            self.set_fill_color(cr, cg, cb)
            self.rect(cx - chord, strip_y, chord * 2, strip_h, "F")

        # borda do círculo
        is_light = rv > 215 and gv > 215 and bv > 215
        self.set_draw_color(155, 148, 138) if is_light else self.set_draw_color(*FAINT)
        self.set_line_width(0.22)
        self.ellipse(cx - r, cy - r, r * 2, r * 2, "D")

    def _draw_cores_full(self, cores: list, y: float) -> float:
        col_w  = CW / 2
        radius = 4.0   # raio do círculo em mm
        row_h  = 11.0  # espaço vertical por linha

        self.set_font("Arial", "", 8)

        for i, cor in enumerate(cores):
            x = MX if i % 2 == 0 else MX + col_w
            if i % 2 == 0 and i > 0:
                y += row_h

            rgb = _cor_rgb(str(cor))
            cx = x + radius
            cy = y + radius
            self._gradient_circle(cx, cy, radius, rgb)

            self.set_xy(x + radius * 2 + 3, cy - 2.5)
            self.set_text_color(*SOFT)
            self.cell(col_w - radius * 2 - 4, 5, str(cor))

        return y + row_h

    # mantém compatibilidade com código antigo
    def product_page(self, product: dict):
        self.product_pages(product)


# ─────────────────────────────────────────────────────────────────────────────

def build_pdf(products: list[dict]) -> bytes:
    pdf = CatalogPDF()
    pdf.cover_page(len(products))
    for p in products:
        pdf.product_pages(p)
    return bytes(pdf.output())

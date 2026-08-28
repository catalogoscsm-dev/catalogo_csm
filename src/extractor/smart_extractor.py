from __future__ import annotations
import json
import base64
from pathlib import Path

import anthropic
from PIL import Image

PROMPT_TECNICA = """Esta é uma página técnica de catálogo de móveis.
Extraia todas as informações do produto visíveis na página.

Responda SOMENTE com JSON válido, sem markdown:
{
  "nome": "nome do produto em maiúsculas",
  "categoria": "categoria (ex: Sofá, Mesa de Centro, Poltrona...)",
  "descricao": "descrição resumida em 1-2 frases valorizando o design",
  "dimensoes": "todas as dimensões/variações separadas por |",
  "materiais": ["material1", "material2"],
  "cores_disponiveis": ["cor1", "cor2"]
}"""

PROMPT_AMBIENTE = """Esta é uma página de foto ambiente de catálogo de móveis.
Identifique o produto principal em destaque.

Responda SOMENTE com JSON válido, sem markdown:
{
  "nome": "nome do produto se visível, ou null",
  "categoria": "categoria inferida pelo visual, ou null",
  "descricao": "descrição breve do que aparece na foto, ou null"
}"""

PROMPT_MISTA = """Esta página de catálogo contém múltiplas fotos E especificações técnicas do mesmo produto.
Extraia todas as informações disponíveis.

Responda SOMENTE com JSON válido, sem markdown:
{
  "nome": "nome do produto em maiúsculas",
  "categoria": "categoria (ex: Sofá, Mesa de Centro, Poltrona...)",
  "descricao": "descrição resumida em 1-2 frases valorizando o design",
  "dimensoes": "todas as dimensões/variações separadas por |",
  "materiais": ["material1", "material2"],
  "cores_disponiveis": ["cor1", "cor2"],
  "num_fotos_na_pagina": 2
}"""

PROMPT_BBOX_FOTOS = """Esta página tem múltiplas fotos de produto.
Identifique as coordenadas de cada foto em porcentagem da página (0.0 a 1.0).

Responda SOMENTE com JSON válido, sem markdown:
{
  "fotos": [
    {"x": 0.0, "y": 0.0, "largura": 0.5, "altura": 0.4},
    {"x": 0.5, "y": 0.0, "largura": 0.5, "altura": 0.4}
  ]
}"""


class SmartExtractor:
    def __init__(self, api_key: str, model: str = "claude-haiku-4-5-20251001"):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model

    # ------------------------------------------------------------------ #
    #  Extração por tipo de página                                         #
    # ------------------------------------------------------------------ #

    def extrair_tecnica(self, imagem_path: Path) -> dict:
        return self._chamar(imagem_path, PROMPT_TECNICA, max_tokens=1024)

    def extrair_ambiente(self, imagem_path: Path) -> dict:
        return self._chamar(imagem_path, PROMPT_AMBIENTE, max_tokens=512)

    def extrair_mista(self, imagem_path: Path) -> dict:
        return self._chamar(imagem_path, PROMPT_MISTA, max_tokens=1024)

    # ------------------------------------------------------------------ #
    #  Recorte de múltiplas fotos de página mista                         #
    # ------------------------------------------------------------------ #

    def recortar_fotos_mista(self, imagem_path: Path, dir_saida: Path, prefixo: str) -> list[Path]:
        """
        Detecta bounding boxes de cada foto na página e recorta individualmente.
        Retorna lista de caminhos das imagens recortadas.
        """
        resultado = self._chamar(imagem_path, PROMPT_BBOX_FOTOS, max_tokens=512)
        fotos_bbox = resultado.get("fotos", [])

        if not fotos_bbox:
            # Fallback: salva a página inteira como única foto
            dest = dir_saida / f"{prefixo}_foto01.jpg"
            self._salvar_como_jpeg(imagem_path, dest)
            return [dest]

        img = Image.open(imagem_path)
        w, h = img.size
        caminhos: list[Path] = []

        for i, bbox in enumerate(fotos_bbox):
            x1 = int(bbox.get("x", 0) * w)
            y1 = int(bbox.get("y", 0) * h)
            x2 = int((bbox.get("x", 0) + bbox.get("largura", 1)) * w)
            y2 = int((bbox.get("y", 0) + bbox.get("altura", 1)) * h)

            # Margem de segurança
            x1 = max(0, x1 - 4)
            y1 = max(0, y1 - 4)
            x2 = min(w, x2 + 4)
            y2 = min(h, y2 + 4)

            if x2 - x1 < 20 or y2 - y1 < 20:
                continue

            recorte = img.crop((x1, y1, x2, y2))
            dest = dir_saida / f"{prefixo}_foto{i+1:02d}.jpg"
            recorte.convert("RGB").save(str(dest), "JPEG", quality=92)
            caminhos.append(dest)

        img.close()
        return caminhos if caminhos else self._fallback_pagina_inteira(imagem_path, dir_saida, prefixo)

    # ------------------------------------------------------------------ #
    #  Interno                                                             #
    # ------------------------------------------------------------------ #

    def _chamar(self, imagem_path: Path, prompt: str, max_tokens: int = 1024) -> dict:
        img_b64, media_type = self._encode(imagem_path)
        for tentativa in range(3):
            try:
                resp = self.client.messages.create(
                    model=self.model,
                    max_tokens=max_tokens,
                    messages=[{
                        "role": "user",
                        "content": [
                            {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": img_b64}},
                            {"type": "text", "text": prompt},
                        ],
                    }],
                )
                texto = resp.content[0].text.strip()
                if texto.startswith("```"):
                    partes = texto.split("```")
                    texto = partes[1][4:] if partes[1].startswith("json") else partes[1]
                return json.loads(texto)
            except Exception:
                if tentativa == 2:
                    return {}
                import time; time.sleep(2)
        return {}

    def _encode(self, path: Path) -> tuple[str, str]:
        suffix = path.suffix.lower()
        media_type = "image/jpeg" if suffix in (".jpg", ".jpeg") else "image/png"
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode(), media_type

    def _salvar_como_jpeg(self, src: Path, dest: Path) -> Path:
        img = Image.open(src)
        img.convert("RGB").save(str(dest), "JPEG", quality=92)
        img.close()
        return dest

    def _fallback_pagina_inteira(self, src: Path, dir_saida: Path, prefixo: str) -> list[Path]:
        dest = dir_saida / f"{prefixo}_foto01.jpg"
        self._salvar_como_jpeg(src, dest)
        return [dest]

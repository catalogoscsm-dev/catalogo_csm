from __future__ import annotations
import base64
import json
import time
from pathlib import Path

import anthropic

from .models import BoundingBox


PROMPT_BBOX = """Você é um sistema de visão computacional especializado em catálogos de móveis planejados.

Analise esta página de catálogo e identifique CADA produto visualmente presente.

Para cada produto encontrado, retorne APENAS um JSON com esta estrutura exata:

{
  "tipo_pagina": "produtos" | "capa" | "indice" | "institucional",
  "multiplos_produtos": true | false,
  "produtos": [
    {
      "nome_parcial": "nome aproximado ou descrição breve do produto",
      "bbox": {
        "x": 0.0,
        "y": 0.0,
        "largura": 0.5,
        "altura": 0.8
      }
    }
  ]
}

REGRAS CRÍTICAS para o bbox (coordenadas em proporção 0.0 a 1.0 da imagem):
- x: distância da borda esquerda
- y: distância do topo
- largura: largura do produto na imagem
- altura: altura do produto na imagem
- Se a página inteira é 1 produto: {"x": 0.0, "y": 0.0, "largura": 1.0, "altura": 1.0}
- Para páginas com grade 2x2: cada produto ocupa ~0.5 de largura e ~0.5 de altura
- Seja preciso: inclua o produto inteiro mas exclua texto de outros produtos vizinhos

Se for capa, índice ou página sem produto físico: retorne {"tipo_pagina": "capa", "multiplos_produtos": false, "produtos": []}

Retorne APENAS o JSON, sem texto adicional, sem markdown, sem explicações."""


class VisionClient:
    """
    Usa Claude Vision (Sonnet) exclusivamente para detecção de
    bounding boxes — localizar onde cada produto está na página.
    É chamado apenas quando há múltiplos produtos por página ou
    quando o bbox é necessário para recorte.
    """

    def __init__(self, api_key: str, model: str = "claude-sonnet-4-6"):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model
        self.max_retries = 3
        self.retry_delay = 5

    def detectar_bboxes(self, imagem_path: Path) -> dict:
        """
        Envia a imagem para Claude Vision e retorna os bboxes dos produtos.
        Retorna dict com estrutura: {tipo_pagina, multiplos_produtos, produtos}
        """
        imagem_b64 = self._encode_image(imagem_path)

        for tentativa in range(self.max_retries):
            try:
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=1024,
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "image",
                                    "source": {
                                        "type": "base64",
                                        "media_type": "image/png",
                                        "data": imagem_b64,
                                    },
                                },
                                {
                                    "type": "text",
                                    "text": PROMPT_BBOX,
                                },
                            ],
                        }
                    ],
                )

                texto = response.content[0].text.strip()
                return self._parse_json(texto)

            except anthropic.RateLimitError:
                if tentativa < self.max_retries - 1:
                    wait = self.retry_delay * (2 ** tentativa)
                    print(f"  Rate limit — aguardando {wait}s...")
                    time.sleep(wait)
                else:
                    raise
            except Exception as e:
                if tentativa < self.max_retries - 1:
                    time.sleep(self.retry_delay)
                else:
                    return {"tipo_pagina": "erro", "multiplos_produtos": False, "produtos": [], "erro": str(e)}

        return {"tipo_pagina": "erro", "multiplos_produtos": False, "produtos": []}

    def _encode_image(self, path: Path) -> str:
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")

    def _parse_json(self, texto: str) -> dict:
        texto = texto.strip()
        # Remove markdown code blocks se presentes
        if texto.startswith("```"):
            linhas = texto.split("\n")
            texto = "\n".join(linhas[1:-1])
        try:
            return json.loads(texto)
        except json.JSONDecodeError:
            # Tenta extrair JSON de dentro do texto
            inicio = texto.find("{")
            fim = texto.rfind("}") + 1
            if inicio != -1 and fim > inicio:
                return json.loads(texto[inicio:fim])
            return {"tipo_pagina": "erro", "multiplos_produtos": False, "produtos": []}

    def bbox_pagina_inteira(self) -> BoundingBox:
        """Bbox padrão quando o produto ocupa a página toda."""
        return BoundingBox(x=0.0, y=0.0, largura=1.0, altura=1.0)

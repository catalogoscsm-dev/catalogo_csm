from __future__ import annotations
import base64
import json
import time
from pathlib import Path

import anthropic

from .models import Produto, BoundingBox, ParteMulticolor


PROMPT_EXTRACAO = """Você é um especialista em catálogos de móveis de alto padrão.

Analise esta imagem (recorte de um catálogo) e extraia TODOS os dados do(s) produto(s) visível(is).

Retorne APENAS um JSON com esta estrutura exata — sem texto adicional, sem markdown:

{
  "produtos": [
    {
      "nome": "nome completo do produto",
      "categoria": "categoria exata do produto (ex: Sofá, Poltrona, Pufe, Mesa de Centro, Mesa Lateral, Mesa de Jantar, Cadeira, Aparador, Rack, Estante, Cama, Criado-mudo, Cômoda, Espelho, Luminária, Tapete, Outros)",
      "descricao": "descrição técnica e comercial completa do produto. Se não houver texto descritivo na imagem, use string vazia.",
      "dimensoes": "copie EXATAMENTE as dimensões como aparecem na imagem, separadas por ' | '. Exemplos: 'P - 115cm x 45cm x h.70cm | G - 155cm x 45cm x h.70cm' ou 'P - Ø40cm x h.45cm | M - Ø50cm x h.45cm'. Preserve o símbolo Ø para produtos circulares.",
      "materiais": ["material 1", "material 2"],
      "cores_disponiveis": ["cor/acabamento 1", "cor 2"],
      "partes_multicolor": [
        {
          "parte": "nome da parte (ex: Estrutura, Tampo, Encosto, Base, Portas)",
          "opcoes": ["opção 1", "opção 2"]
        }
      ],
      "multiplos_na_pagina": false
    }
  ]
}

REGRAS:
- Se a imagem tiver mais de um produto, liste cada um separadamente em "produtos"
- dimensoes: copie o texto exatamente como está na imagem — não reformate, não converta unidades
- partes_multicolor: preencha APENAS se partes diferentes do móvel têm cores/materiais independentes
- Se todas as cores se aplicam ao produto inteiro, use apenas "cores_disponiveis" e deixe partes_multicolor como []
- Capture TODAS as variações de tamanho (P, M, G, GG, etc.)
- materiais: separe cada material individual como item da lista
- Se não encontrar alguma informação, use string vazia "" ou lista vazia [] — não invente dados

Retorne APENAS o JSON. Nenhum texto antes ou depois."""


class TextClient:
    """
    Usa Claude Haiku (Vision) para extrair dados textuais completos dos produtos.
    Recebe a imagem recortada do produto e retorna JSON estruturado.
    """

    def __init__(self, api_key: str, model: str = "claude-haiku-4-5-20251001"):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model
        self.max_retries = 3
        self.retry_delay = 3

    def extrair_dados(self, imagem_path: Path) -> list[dict]:
        """
        Recebe imagem (pode ser página inteira ou recorte de produto).
        Retorna lista de dicts com dados dos produtos encontrados.
        """
        imagem_b64, media_type = self._encode_image(imagem_path)

        for tentativa in range(self.max_retries):
            try:
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=4096,
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "image",
                                    "source": {
                                        "type": "base64",
                                        "media_type": media_type,
                                        "data": imagem_b64,
                                    },
                                },
                                {
                                    "type": "text",
                                    "text": PROMPT_EXTRACAO,
                                },
                            ],
                        }
                    ],
                )

                texto = response.content[0].text.strip()
                dados = self._parse_json(texto)
                return dados.get("produtos", [])

            except anthropic.RateLimitError:
                if tentativa < self.max_retries - 1:
                    wait = self.retry_delay * (2 ** tentativa)
                    print(f"  Rate limit Claude Haiku (tentativa {tentativa+1}) — aguardando {wait}s")
                    time.sleep(wait)
                else:
                    print("  Falha definitiva: rate limit persistente")
                    return []
            except Exception as e:
                if tentativa < self.max_retries - 1:
                    wait = self.retry_delay * (2 ** tentativa)
                    print(f"  Erro Claude Haiku (tentativa {tentativa+1}): {e} — aguardando {wait}s")
                    time.sleep(wait)
                else:
                    print(f"  Falha definitiva Claude Haiku: {e}")
                    return []

        return []

    def _encode_image(self, path: Path) -> tuple[str, str]:
        suffix = path.suffix.lower()
        media_type = "image/jpeg" if suffix in (".jpg", ".jpeg") else "image/png"
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8"), media_type

    def _parse_json(self, texto: str) -> dict:
        texto = texto.strip()
        if texto.startswith("```"):
            linhas = texto.split("\n")
            texto = "\n".join(linhas[1:-1])
        try:
            return json.loads(texto)
        except json.JSONDecodeError:
            inicio = texto.find("{")
            fim = texto.rfind("}") + 1
            if inicio != -1 and fim > inicio:
                try:
                    return json.loads(texto[inicio:fim])
                except Exception:
                    pass
            return {"produtos": []}

    def dict_to_produto(self, dados: dict, bbox: BoundingBox, pagina: int, pdf_origem: str, fornecedor: str) -> Produto:
        """Converte dict retornado pela IA em objeto Produto."""
        partes = [
            ParteMulticolor(parte=p["parte"], opcoes=p.get("opcoes", []))
            for p in dados.get("partes_multicolor", [])
        ]

        return Produto(
            nome=dados.get("nome", ""),
            categoria=dados.get("categoria", ""),
            descricao=dados.get("descricao", ""),
            dimensoes=dados.get("dimensoes", ""),
            materiais=dados.get("materiais", []),
            cores_disponiveis=dados.get("cores_disponiveis", []),
            partes_multicolor=partes,
            bbox=bbox,
            pagina_origem=pagina,
            pdf_origem=pdf_origem,
            fornecedor_interno=fornecedor,
        )

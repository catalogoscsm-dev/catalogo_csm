from __future__ import annotations
import json
import base64
from pathlib import Path

import anthropic

PROMPT_CLASSIFICAR = """Analise esta página de catálogo de móveis e classifique-a em uma das categorias abaixo.

TIPOS:
- "capa"     : página de capa, contra-capa ou folha de rosto
- "indice"   : sumário ou índice de categorias
- "ambiente" : foto do produto em uso/decorado num ambiente (pode ter nome, pode não ter specs)
- "tecnica"  : especificações técnicas, dimensões, tabela de medidas — com foto(s) em fundo branco/neutro
- "mista"    : contém NA MESMA PÁGINA tanto fotos do produto (múltiplos ângulos) E especificações técnicas
- "vazia"    : página sem conteúdo relevante de produto (separador, cor sólida, texto institucional)

Identifique também o nome do produto SE aparecer claramente na página.

Responda SOMENTE com JSON válido, sem markdown:
{"tipo": "...", "nome_produto": "NOME EM MAIÚSCULAS ou null"}"""


class PageClassifier:
    def __init__(self, api_key: str, model: str = "claude-haiku-4-5-20251001"):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model

    def classificar(self, imagem_path: Path) -> dict:
        """
        Retorna {"tipo": str, "nome_produto": str | None}.
        """
        img_b64, media_type = self._encode(imagem_path)
        for tentativa in range(3):
            try:
                resp = self.client.messages.create(
                    model=self.model,
                    max_tokens=256,
                    messages=[{
                        "role": "user",
                        "content": [
                            {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": img_b64}},
                            {"type": "text", "text": PROMPT_CLASSIFICAR},
                        ],
                    }],
                )
                texto = resp.content[0].text.strip()
                # Remove possível markdown ```json ... ```
                if texto.startswith("```"):
                    texto = texto.split("```")[1]
                    if texto.startswith("json"):
                        texto = texto[4:]
                dados = json.loads(texto)
                tipo = dados.get("tipo", "vazia")
                nome = dados.get("nome_produto") or None
                if nome:
                    nome = nome.strip().upper()
                return {"tipo": tipo, "nome_produto": nome}
            except Exception as e:
                if tentativa == 2:
                    return {"tipo": "vazia", "nome_produto": None}
                import time; time.sleep(2)

    def _encode(self, path: Path) -> tuple[str, str]:
        suffix = path.suffix.lower()
        media_type = "image/jpeg" if suffix in (".jpg", ".jpeg") else "image/png"
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode(), media_type

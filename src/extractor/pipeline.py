from __future__ import annotations
import json
import time
from pathlib import Path
from datetime import datetime

from .models import Produto, BoundingBox, ResultadoPDF
from .pdf_processor import PDFProcessor
from .vision_client import VisionClient
from .text_client import TextClient
from .image_cropper import ImageCropper
from .color_extractor import ColorExtractor
from .checkpoint import Checkpoint


class Pipeline:
    """
    Orquestra o fluxo completo:

    PDF → Imagens (PyMuPDF)
        → Claude Sonnet (bbox por produto)
        → Recorte (Pillow)
        → Claude Haiku (dados textuais)
        → ColorThief (paleta)
        → JSON final por produto
    """

    # Páginas que claramente não têm produto (detectadas pelo Claude Vision)
    TIPOS_SEM_PRODUTO = {"capa", "indice", "institucional", "erro"}

    def __init__(
        self,
        claude_api_key: str,
        output_dir: Path,
        checkpoint_dir: Path,
        dpi: int = 200,
        num_cores_paleta: int = 5,
        delay_entre_paginas: float = 1.0,
    ):
        self.pdf_processor = PDFProcessor(dpi=dpi)
        self.vision = VisionClient(api_key=claude_api_key)
        self.text = TextClient(api_key=claude_api_key)
        self.cropper = ImageCropper()
        self.colors = ColorExtractor(num_cores=num_cores_paleta)
        self.output_dir = output_dir
        self.checkpoint_dir = checkpoint_dir
        self.delay = delay_entre_paginas
        output_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------ #
    #  Ponto de entrada principal                                          #
    # ------------------------------------------------------------------ #

    def processar_pdf(
        self,
        pdf_path: Path,
        fornecedor: str = "",
        retomar: bool = True,
    ) -> ResultadoPDF:
        """
        Processa um PDF completo e retorna ResultadoPDF com todos os produtos.
        Se retomar=True e existir checkpoint, continua de onde parou.
        """
        pdf_name = pdf_path.stem
        fornecedor = fornecedor or pdf_name

        total_paginas = self.pdf_processor.total_paginas(pdf_path)
        resultado = ResultadoPDF(
            pdf_path=str(pdf_path),
            fornecedor=fornecedor,
            total_paginas=total_paginas,
        )

        # Diretórios de saída para este PDF
        dir_paginas  = self.output_dir / pdf_name / "paginas"
        dir_produtos = self.output_dir / pdf_name / "produtos"
        dir_paginas.mkdir(parents=True, exist_ok=True)
        dir_produtos.mkdir(parents=True, exist_ok=True)

        # Checkpoint
        ckpt = Checkpoint(self.checkpoint_dir, pdf_name)
        pagina_inicial = 1
        produtos_acumulados: list[dict] = []

        if retomar and ckpt.existe():
            dados_ckpt = ckpt.carregar()
            pagina_inicial = dados_ckpt["ultima_pagina_processada"] + 1
            produtos_acumulados = dados_ckpt.get("produtos", [])
            print(f"  ↩  Retomando do checkpoint: página {pagina_inicial} ({len(produtos_acumulados)} produtos já salvos)")

        print(f"\n{'='*60}")
        print(f"PDF: {pdf_path.name}")
        print(f"Fornecedor: {fornecedor}")
        print(f"Total de páginas: {total_paginas}")
        print(f"Início: página {pagina_inicial}")
        print(f"{'='*60}")

        try:
            for pagina_num in range(pagina_inicial, total_paginas + 1):
                print(f"\n  [{pagina_num}/{total_paginas}] Processando página...", end="", flush=True)

                produtos_pagina = self._processar_pagina(
                    pdf_path=pdf_path,
                    pagina_num=pagina_num,
                    dir_paginas=dir_paginas,
                    dir_produtos=dir_produtos,
                    fornecedor=fornecedor,
                )

                if produtos_pagina:
                    print(f" ✓ {len(produtos_pagina)} produto(s) extraído(s)", end="")
                    produtos_acumulados.extend([p.to_dict() for p in produtos_pagina])
                    resultado.produtos.extend(produtos_pagina)
                else:
                    print(f" – sem produto", end="")

                resultado.paginas_processadas += 1

                # Checkpoint
                if ckpt.deve_salvar(pagina_num):
                    ckpt.salvar(pagina_num, produtos_acumulados)
                    print(f" [checkpoint salvo]", end="")

                if self.delay > 0:
                    time.sleep(self.delay)

        except KeyboardInterrupt:
            print("\n\n⚠  Interrompido pelo usuário. Salvando checkpoint...")
            ckpt.salvar(resultado.paginas_processadas, produtos_acumulados)
            raise

        # Salva JSON final
        self._salvar_resultado(resultado, pdf_name)
        ckpt.deletar()

        print(f"\n\n✅ Concluído: {len(resultado.produtos)} produtos extraídos de {pdf_path.name}")
        return resultado

    # ------------------------------------------------------------------ #
    #  Processamento de uma página                                         #
    # ------------------------------------------------------------------ #

    def _processar_pagina(
        self,
        pdf_path: Path,
        pagina_num: int,
        dir_paginas: Path,
        dir_produtos: Path,
        fornecedor: str,
    ) -> list[Produto]:
        """
        Fluxo por página:
        1. Converte página em imagem
        2. Chama Claude Vision → detecta bboxes
        3. Para cada produto: recorta + chama DeepSeek + extrai paleta
        """
        # Etapa 1: PDF → Imagem
        pagina_img = self.pdf_processor.converter_pagina(pdf_path, pagina_num, dir_paginas)

        # Etapa 2: Claude Vision → bboxes
        deteccao = self.vision.detectar_bboxes(pagina_img.caminho)

        tipo_pagina = deteccao.get("tipo_pagina", "produtos")
        if tipo_pagina in self.TIPOS_SEM_PRODUTO:
            return []

        produtos_detectados = deteccao.get("produtos", [])

        # Se Claude Vision não retornou produtos mas a página não é capa/índice,
        # trata como produto único ocupando a página inteira
        if not produtos_detectados:
            produtos_detectados = [{"nome_parcial": "", "bbox": {"x": 0.0, "y": 0.0, "largura": 1.0, "altura": 1.0}}]

        produtos_extraidos: list[Produto] = []
        pdf_stem = pdf_path.stem

        for idx, det in enumerate(produtos_detectados):
            bbox_dict = det.get("bbox", {})
            bbox = BoundingBox(
                x=bbox_dict.get("x", 0.0),
                y=bbox_dict.get("y", 0.0),
                largura=bbox_dict.get("largura", 1.0),
                altura=bbox_dict.get("altura", 1.0),
            )

            # Etapa 3: Recorte da imagem do produto
            nome_arquivo = f"{pdf_stem}_pag{pagina_num:03d}_prod{idx+1:02d}.jpg"
            caminho_recorte = dir_produtos / nome_arquivo

            if bbox.is_valid() and (bbox.largura < 0.99 or bbox.altura < 0.99):
                self.cropper.recortar(pagina_img.caminho, bbox, caminho_recorte)
            else:
                self.cropper.recortar_pagina_inteira(pagina_img.caminho, caminho_recorte)

            # Etapa 4: DeepSeek → dados textuais
            dados_lista = self.text.extrair_dados(caminho_recorte)

            if not dados_lista:
                # Fallback: usa nome parcial detectado pelo Claude Vision
                dados_lista = [{"nome": det.get("nome_parcial", f"Produto pág.{pagina_num}"), "categoria": "", "descricao": "", "dimensoes": "", "materiais": [], "cores_disponiveis": [], "partes_multicolor": []}]

            for dados in dados_lista:
                produto = self.text.dict_to_produto(
                    dados=dados,
                    bbox=bbox,
                    pagina=pagina_num,
                    pdf_origem=pdf_path.name,
                    fornecedor=fornecedor,
                )
                produto.imagem_path = str(caminho_recorte.relative_to(self.output_dir))

                # Etapa 5: ColorThief → paleta
                produto.paleta_hex = self.colors.extrair_paleta(caminho_recorte)

                produtos_extraidos.append(produto)

        return produtos_extraidos

    # ------------------------------------------------------------------ #
    #  Persistência                                                        #
    # ------------------------------------------------------------------ #

    def _salvar_resultado(self, resultado: ResultadoPDF, pdf_name: str) -> Path:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        caminho = self.output_dir / pdf_name / f"resultado_{timestamp}.json"

        with open(caminho, "w", encoding="utf-8") as f:
            json.dump(resultado.to_dict(), f, ensure_ascii=False, indent=2)

        print(f"  💾 JSON salvo em: {caminho}")
        return caminho

    # ------------------------------------------------------------------ #
    #  Processamento em lote                                               #
    # ------------------------------------------------------------------ #

    def processar_lote(self, pdf_paths: list[Path], fornecedores: dict[str, str] | None = None) -> list[ResultadoPDF]:
        """
        Processa múltiplos PDFs em sequência.
        fornecedores: dict {nome_pdf_sem_extensao: nome_fornecedor}
        """
        fornecedores = fornecedores or {}
        resultados = []

        for i, pdf_path in enumerate(pdf_paths):
            print(f"\n\n{'#'*60}")
            print(f"PDF {i+1}/{len(pdf_paths)}: {pdf_path.name}")
            print(f"{'#'*60}")

            fornecedor = fornecedores.get(pdf_path.stem, pdf_path.stem)
            try:
                resultado = self.processar_pdf(pdf_path, fornecedor=fornecedor)
                resultados.append(resultado)
            except Exception as e:
                print(f"\n❌ Erro processando {pdf_path.name}: {e}")
                resultados.append(ResultadoPDF(
                    pdf_path=str(pdf_path),
                    fornecedor=fornecedor,
                    total_paginas=0,
                    erros=[{"erro": str(e)}],
                ))

        # Relatório final consolidado
        self._salvar_relatorio_consolidado(resultados)
        return resultados

    def _salvar_relatorio_consolidado(self, resultados: list[ResultadoPDF]) -> None:
        total_produtos = sum(len(r.produtos) for r in resultados)
        relatorio = {
            "gerado_em": datetime.now().isoformat(),
            "total_pdfs": len(resultados),
            "total_produtos": total_produtos,
            "por_pdf": [
                {
                    "pdf": r.pdf_path,
                    "fornecedor": r.fornecedor,
                    "paginas": r.total_paginas,
                    "produtos": len(r.produtos),
                    "erros": len(r.erros),
                }
                for r in resultados
            ],
        }
        caminho = self.output_dir / "relatorio_consolidado.json"
        with open(caminho, "w", encoding="utf-8") as f:
            json.dump(relatorio, f, ensure_ascii=False, indent=2)
        print(f"\n📊 Relatório consolidado: {caminho}")
        print(f"   Total de produtos extraídos: {total_produtos}")

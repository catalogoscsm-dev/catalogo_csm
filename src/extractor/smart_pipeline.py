from __future__ import annotations
import json
import time
from pathlib import Path
from datetime import datetime
from PIL import Image

from .pdf_processor import PDFProcessor
from .page_classifier import PageClassifier
from .smart_extractor import SmartExtractor
from .product_merger import ProductMerger, PageResult
from .checkpoint import Checkpoint


class SmartPipeline:
    """
    Pipeline inteligente de extração de produtos de PDFs de catálogos.

    Estratégia página por página:
      1. Renderiza cada página como PNG
      2. Classifica: capa / indice / ambiente / tecnica / mista / vazia
      3. Extrai dados adaptados ao tipo
      4. Recorta imagens (múltiplas se página mista)
      5. Agrupa páginas pelo nome do produto
      6. Gera JSON final compatível com o webapp

    Funciona com qualquer estrutura de catálogo — 1 ou 2 páginas por produto,
    especificações separadas ou juntas com as fotos.
    """

    TIPOS_SEM_PRODUTO = {"capa", "indice", "vazia"}

    def __init__(
        self,
        claude_api_key: str,
        output_dir: Path,
        checkpoint_dir: Path,
        dpi: int = 150,
        delay_entre_paginas: float = 0.8,
    ):
        self.pdf_proc  = PDFProcessor(dpi=dpi)
        self.classifier = PageClassifier(api_key=claude_api_key)
        self.extractor  = SmartExtractor(api_key=claude_api_key)
        self.merger     = ProductMerger()
        self.output_dir = output_dir
        self.ckpt_dir   = checkpoint_dir
        self.delay      = delay_entre_paginas

    # ------------------------------------------------------------------ #
    #  Entrada principal                                                   #
    # ------------------------------------------------------------------ #

    def processar_pdf(
        self,
        pdf_path: Path,
        fornecedor: str = "",
        retomar: bool = True,
    ) -> dict:
        """
        Processa o PDF completo e salva resultado JSON.
        Retorna dicionário com produtos e metadados.
        """
        pdf_name   = pdf_path.stem
        fornecedor = fornecedor or pdf_name
        total_pags = self.pdf_proc.total_paginas(pdf_path)

        dir_paginas  = self.output_dir / pdf_name / "paginas"
        dir_imagens  = self.output_dir / pdf_name / "imagens"
        dir_paginas.mkdir(parents=True, exist_ok=True)
        dir_imagens.mkdir(parents=True, exist_ok=True)

        ckpt = Checkpoint(self.ckpt_dir, f"smart_{pdf_name}")
        pagina_inicial = 1
        resultados_salvos: list[dict] = []

        if retomar and ckpt.existe():
            dados_ckpt = ckpt.carregar()
            pagina_inicial = dados_ckpt["ultima_pagina_processada"] + 1
            resultados_salvos = dados_ckpt.get("page_results", [])
            print(f"  ↩  Retomando checkpoint: página {pagina_inicial}")

        print(f"\n{'='*60}")
        print(f"PDF: {pdf_path.name}  |  {total_pags} páginas  |  fornecedor: {fornecedor}")
        print(f"{'='*60}")

        page_results: list[PageResult] = [PageResult(**r) for r in resultados_salvos]

        try:
            for num in range(pagina_inicial, total_pags + 1):
                result = self._processar_pagina(
                    pdf_path=pdf_path,
                    pagina_num=num,
                    dir_paginas=dir_paginas,
                    dir_imagens=dir_imagens,
                    pdf_name=pdf_name,
                )
                page_results.append(result)

                tipo_label = result.tipo.ljust(8)
                nome_label = result.nome_produto or "—"
                imgs_label = f"{len(result.imagens)} img(s)"
                print(f"  [{num:03d}/{total_pags}] {tipo_label}  {nome_label:<30}  {imgs_label}")

                if ckpt.deve_salvar(num):
                    ckpt.salvar(num, [self._pr_to_dict(r) for r in page_results])

                if self.delay:
                    time.sleep(self.delay)

        except KeyboardInterrupt:
            print("\n⚠  Interrompido. Salvando checkpoint...")
            ckpt.salvar(page_results[-1].pagina if page_results else 0,
                        [self._pr_to_dict(r) for r in page_results])
            raise

        # Agrupa páginas em produtos
        produtos = self.merger.merge(page_results, str(pdf_path), fornecedor)
        print(f"\n✅ {len(produtos)} produto(s) identificado(s) em {pdf_path.name}")

        resultado = self._salvar_resultado(produtos, pdf_path, fornecedor, total_pags)
        ckpt.deletar()
        return resultado

    # ------------------------------------------------------------------ #
    #  Processamento de uma página                                         #
    # ------------------------------------------------------------------ #

    def _processar_pagina(
        self,
        pdf_path: Path,
        pagina_num: int,
        dir_paginas: Path,
        dir_imagens: Path,
        pdf_name: str,
    ) -> PageResult:

        # Renderiza página → PNG
        pagina_img = self.pdf_proc.converter_pagina(pdf_path, pagina_num, dir_paginas)
        img_path   = pagina_img.caminho
        prefixo    = f"{pdf_name}_pag{pagina_num:03d}"

        # Classifica
        classif  = self.classifier.classificar(img_path)
        tipo     = classif.get("tipo", "vazia")
        nome     = classif.get("nome_produto")

        # Páginas sem produto: retorna sem extrair mais nada
        if tipo in self.TIPOS_SEM_PRODUTO:
            return PageResult(pagina=pagina_num, tipo=tipo, nome_produto=nome, dados={}, imagens=[])

        dados: dict   = {}
        imagens: list[str] = []

        if tipo == "ambiente":
            dados  = self.extractor.extrair_ambiente(img_path)
            # Salva a página inteira como imagem ambiente
            dest   = dir_imagens / f"{prefixo}_amb.jpg"
            self._png_to_jpeg(img_path, dest)
            imagens = [self._rel(dest)]

        elif tipo == "tecnica":
            dados  = self.extractor.extrair_tecnica(img_path)
            dest   = dir_imagens / f"{prefixo}_tec.jpg"
            self._png_to_jpeg(img_path, dest)
            imagens = [self._rel(dest)]

        elif tipo == "mista":
            dados = self.extractor.extrair_mista(img_path)
            # Salva a página inteira — fotos individuais não são recortadas
            dest  = dir_imagens / f"{prefixo}_tec.jpg"
            self._png_to_jpeg(img_path, dest)
            imagens = [self._rel(dest)]

        # Consolida nome: prefere o da classificação, senão usa o extraído dos dados
        if not nome:
            nome = (dados.get("nome") or "").strip().upper() or None

        return PageResult(
            pagina=pagina_num,
            tipo=tipo,
            nome_produto=nome,
            dados=dados,
            imagens=imagens,
        )

    # ------------------------------------------------------------------ #
    #  Persistência                                                        #
    # ------------------------------------------------------------------ #

    def _salvar_resultado(
        self,
        produtos,
        pdf_path: Path,
        fornecedor: str,
        total_pags: int,
    ) -> dict:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        pdf_name  = pdf_path.stem
        caminho   = self.output_dir / pdf_name / f"resultado_{timestamp}.json"

        resultado = {
            "pdf_path": str(pdf_path),
            "fornecedor": fornecedor,
            "total_paginas": total_pags,
            "paginas_processadas": total_pags,
            "produtos": [p.to_dict() for p in produtos],
        }

        with open(caminho, "w", encoding="utf-8") as f:
            json.dump(resultado, f, ensure_ascii=False, indent=2)

        print(f"  💾 JSON salvo: {caminho}")
        return resultado

    # ------------------------------------------------------------------ #
    #  Utilitários                                                         #
    # ------------------------------------------------------------------ #

    def _png_to_jpeg(self, src: Path, dest: Path) -> None:
        img = Image.open(src)
        img.convert("RGB").save(str(dest), "JPEG", quality=90)
        img.close()

    def _rel(self, path: Path) -> str:
        """Retorna path relativo a data/ para armazenar no JSON."""
        try:
            return path.relative_to(self.output_dir.parent).as_posix()
        except ValueError:
            return path.as_posix()

    @staticmethod
    def _pr_to_dict(r: PageResult) -> dict:
        return {
            "pagina": r.pagina,
            "tipo": r.tipo,
            "nome_produto": r.nome_produto,
            "dados": r.dados,
            "imagens": r.imagens,
        }

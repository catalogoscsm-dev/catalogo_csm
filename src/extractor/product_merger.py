from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class PageResult:
    """Resultado do processamento de uma única página."""
    pagina: int
    tipo: str                          # ambiente | tecnica | mista | capa | indice | vazia
    nome_produto: str | None
    dados: dict                        # campos extraídos (nome, categoria, dimensoes, ...)
    imagens: list[str]                 # caminhos das imagens recortadas/salvas desta página


@dataclass
class ProdutoBruto:
    """Produto montado pela fusão de páginas relacionadas."""
    nome: str
    categoria: str
    descricao: str
    dimensoes: str
    materiais: list[str]
    cores_disponiveis: list[str]
    imagens: list[str]                 # todas as fotos (ambiente primeiro, tecnica depois)
    paginas_origem: list[int]
    pdf_origem: str
    fornecedor: str

    def to_dict(self) -> dict:
        return {
            "nome": self.nome,
            "categoria": self.categoria,
            "descricao": self.descricao,
            "dimensoes": self.dimensoes,
            "materiais": self.materiais,
            "cores_disponiveis": self.cores_disponiveis,
            "paleta_hex": [],
            "imagem_path": self.imagens[0] if self.imagens else "",
            "imagens": self.imagens,
            "pagina_origem": self.paginas_origem[0] if self.paginas_origem else 0,
            "pdf_origem": self.pdf_origem,
            "fornecedor": self.fornecedor,
            "aprovado": 1,
        }


class ProductMerger:
    """
    Agrupa PageResults em ProdutoBrutos usando duas estratégias:

    1. Por nome: páginas com o mesmo nome_produto são agrupadas.
    2. Por proximidade: páginas sem nome são encostadas na página nomeada mais próxima
       (ambiente adjacente a técnica).
    """

    TIPOS_SEM_PRODUTO = {"capa", "indice", "vazia"}

    def merge(
        self,
        paginas: list[PageResult],
        pdf_origem: str,
        fornecedor: str,
    ) -> list[ProdutoBruto]:

        # 1. Descarta páginas irrelevantes
        relevantes = [p for p in paginas if p.tipo not in self.TIPOS_SEM_PRODUTO]

        if not relevantes:
            return []

        # 2. Propaga nome para páginas sem nome usando vizinhos
        self._propagar_nomes(relevantes)

        # 3. Agrupa por nome
        grupos: dict[str, list[PageResult]] = {}
        sem_nome: list[PageResult] = []

        for p in relevantes:
            chave = (p.nome_produto or "").strip().upper()
            if chave:
                grupos.setdefault(chave, []).append(p)
            else:
                sem_nome.append(p)

        # Páginas que ficaram sem nome viram produtos individuais
        for p in sem_nome:
            label = f"PRODUTO_PAG{p.pagina:03d}"
            grupos.setdefault(label, []).append(p)

        # 4. Funde cada grupo em um ProdutoBruto
        produtos: list[ProdutoBruto] = []
        for nome_grupo, grupo in grupos.items():
            produto = self._fundir_grupo(nome_grupo, grupo, pdf_origem, fornecedor)
            produtos.append(produto)

        # Ordena pela primeira página de cada produto
        produtos.sort(key=lambda p: p.paginas_origem[0])
        return produtos

    # ------------------------------------------------------------------ #
    #  Propagação de nome entre páginas adjacentes                         #
    # ------------------------------------------------------------------ #

    def _propagar_nomes(self, paginas: list[PageResult]) -> None:
        """
        Páginas sem nome recebem o nome da página nomeada mais próxima,
        desde que estejam a no máximo 2 posições de distância.
        """
        n = len(paginas)

        # Passa para frente
        ultimo_nome: str | None = None
        ultima_pos: int = -99
        for i, p in enumerate(paginas):
            if p.nome_produto:
                ultimo_nome = p.nome_produto
                ultima_pos = i
            elif ultimo_nome and (i - ultima_pos) <= 2:
                p.nome_produto = ultimo_nome

        # Passa para trás (preenche ambiente que vem ANTES da técnica)
        proximo_nome: str | None = None
        proxima_pos: int = 99999
        for i in range(n - 1, -1, -1):
            p = paginas[i]
            if p.nome_produto:
                proximo_nome = p.nome_produto
                proxima_pos = i
            elif proximo_nome and (proxima_pos - i) <= 2:
                p.nome_produto = proximo_nome

    # ------------------------------------------------------------------ #
    #  Fusão de grupo de páginas → produto único                           #
    # ------------------------------------------------------------------ #

    def _fundir_grupo(
        self,
        nome_grupo: str,
        grupo: list[PageResult],
        pdf_origem: str,
        fornecedor: str,
    ) -> ProdutoBruto:

        # Página técnica ou mista tem prioridade para dados textuais
        tecnicas = [p for p in grupo if p.tipo in ("tecnica", "mista")]
        ambientes = [p for p in grupo if p.tipo == "ambiente"]

        fonte_dados = tecnicas[0] if tecnicas else grupo[0]
        dados = fonte_dados.dados

        nome       = self._campo(dados, "nome") or nome_grupo
        categoria  = self._campo(dados, "categoria") or ""
        descricao  = self._campo(dados, "descricao") or ""
        dimensoes  = self._campo(dados, "dimensoes") or ""
        materiais  = dados.get("materiais") or []
        cores      = dados.get("cores_disponiveis") or []

        # Enriquece descrição a partir de página ambiente se a técnica não trouxe
        if not descricao and ambientes:
            descricao = self._campo(ambientes[0].dados, "descricao") or ""

        # Monta lista de imagens: ambientes primeiro (mais bonitas), técnicas depois
        imagens: list[str] = []
        for p in ambientes:
            imagens.extend(p.imagens)
        for p in tecnicas:
            imagens.extend(p.imagens)
        # Páginas sem tipo definido contribuem com imagens ao final
        outros = [p for p in grupo if p.tipo not in ("ambiente", "tecnica", "mista")]
        for p in outros:
            imagens.extend(p.imagens)

        # Remove duplicatas mantendo ordem
        vistas: set[str] = set()
        imagens_unicas: list[str] = []
        for img in imagens:
            if img not in vistas:
                vistas.add(img)
                imagens_unicas.append(img)

        paginas_origem = sorted(set(p.pagina for p in grupo))

        return ProdutoBruto(
            nome=nome,
            categoria=categoria,
            descricao=descricao,
            dimensoes=dimensoes,
            materiais=materiais if isinstance(materiais, list) else [materiais],
            cores_disponiveis=cores if isinstance(cores, list) else [cores],
            imagens=imagens_unicas,
            paginas_origem=paginas_origem,
            pdf_origem=pdf_origem,
            fornecedor=fornecedor,
        )

    @staticmethod
    def _campo(dados: dict, chave: str) -> str:
        valor = dados.get(chave)
        if not valor:
            return ""
        return str(valor).strip()

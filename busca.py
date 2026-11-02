"""
Índice e busca híbrida:
  - BM25 (palavras-chave, funciona sempre, offline)
  - Embeddings multilíngues (opcional: pip install sentence-transformers)
Os rankings são combinados por Reciprocal Rank Fusion (RRF).

- Buscador: artigos (PDF), índice salvo em .indice/ (python rag.py indexar)
- BuscadorMemoria: seus READMEs de contexto, indexados na hora (não precisa reindexar)
"""
from __future__ import annotations

import json
import pickle
import re
import unicodedata
from typing import Callable, Iterable

from rank_bm25 import BM25Okapi, BM25Plus

import config

STOPWORDS = set("""
a ao aos as ate com como da das de dela dele deles do dos e ela elas ele eles em
entre era essa esse esta este eu foi for ha isso isto ja la lhe mais mas me mesmo
meu na nas nao nem no nos o os ou para pela pelas pelo pelos por qual quando que
quem se sem ser seu seus si so sua suas tambem te tem ter um uma umas uns voce
sao foram sobre ainda apos onde pois seja sido estao estar the of and in to is
for on with by an be are this that from as at or it
""".split())


def tokenizar(texto: str) -> list[str]:
    t = unicodedata.normalize("NFKD", texto.lower()).encode("ascii", "ignore").decode()
    tokens = re.findall(r"[a-z0-9]+", t)
    # radical simples: corta plural/sufixos comuns sem depender de libs extras
    out = []
    for tok in tokens:
        if tok in STOPWORDS or len(tok) < 2:
            continue
        for suf in ("mente", "coes", "cao", "oes", "res", "es", "s"):
            if tok.endswith(suf) and len(tok) - len(suf) >= 4:
                tok = tok[: -len(suf)]
                break
        out.append(tok)
    return out


# ------------------------------------------------------------ embeddings
_modelo = None


def _embedder():
    global _modelo
    if not config.USAR_EMBEDDINGS:
        return None
    if _modelo is None:
        try:
            from sentence_transformers import SentenceTransformer
            _modelo = SentenceTransformer(config.MODELO_EMBEDDINGS)
        except Exception:
            _modelo = False
    return _modelo or None


def _vetorizar(textos: list[str], barra: bool = False):
    emb = _embedder()
    if not emb or not textos:
        return None
    return emb.encode(["passage: " + t for t in textos],
                      normalize_embeddings=True, show_progress_bar=barra)


# ------------------------------------------------------------ índice dos artigos
def construir(chunks: list[dict]) -> None:
    config.PASTA_INDICE.mkdir(exist_ok=True)
    tokens = [tokenizar(c["texto"]) for c in chunks]
    with open(config.PASTA_INDICE / "bm25.pkl", "wb") as f:
        pickle.dump({"chunks": chunks, "tokens": tokens}, f)

    vet = _vetorizar([c["texto"] for c in chunks], barra=True)
    if vet is not None:
        import numpy as np
        np.save(config.PASTA_INDICE / "emb.npy", vet)
        print(f"  índice semântico: {len(chunks)} trechos")
    else:
        (config.PASTA_INDICE / "emb.npy").unlink(missing_ok=True)
        print("  índice só por palavras-chave (instale sentence-transformers para busca semântica)")
    print(f"  índice BM25: {len(chunks)} trechos")


# ------------------------------------------------------------ busca
class _BuscaBase:
    chunks: list[dict]
    bm25: BM25Okapi | None
    vet = None

    def _preparar(self, tokens: list[list[str]], classe=BM25Okapi):
        # BM25 quebra com corpus vazio (ou só com textos vazios)
        self.bm25 = classe(tokens) if any(tokens) else None
        self.termos = [set(t) for t in tokens]

    def buscar_multi(self, consultas: Iterable[str], k: int,
                     filtro: Callable[[dict], bool] | None = None,
                     max_por_fonte: int | None = None) -> list[dict]:
        """Busca com várias consultas ao mesmo tempo, fundindo tudo por RRF."""
        consultas = [c for c in consultas if c and c.strip()]
        if not self.chunks or not consultas or k <= 0:
            return []
        validos = [i for i, c in enumerate(self.chunks) if filtro is None or filtro(c)]
        if not validos:
            return []
        rankings, com_termo = [], set()
        emb = _embedder() if self.vet is not None else None
        for consulta in consultas:
            if self.bm25 is not None:
                q = tokenizar(consulta)
                notas = self.bm25.get_scores(q)
                qs = set(q)
                com_termo.update(i for i in validos if self.termos[i] & qs)
                rankings.append(sorted(validos, key=lambda i: -notas[i])[:60])
            if emb is not None:
                q = emb.encode(["query: " + consulta], normalize_embeddings=True)[0]
                sims = self.vet @ q
                rankings.append(sorted(validos, key=lambda i: -sims[i])[:60])

        fusao: dict[int, float] = {}
        for r in rankings:
            for pos, i in enumerate(r):
                fusao[i] = fusao.get(i, 0) + 1 / (60 + pos)
        melhores = sorted(fusao, key=lambda i: -fusao[i])
        if emb is None:  # só BM25: descarta trechos sem nenhum termo em comum
            melhores = [i for i in melhores if i in com_termo]

        saida, por_fonte = [], {}
        for i in melhores:
            c = self.chunks[i]
            if max_por_fonte and por_fonte.get(c["fonte"], 0) >= max_por_fonte:
                continue
            por_fonte[c["fonte"]] = por_fonte.get(c["fonte"], 0) + 1
            saida.append(c)
            if len(saida) >= k:
                break
        return saida

    def buscar(self, pergunta: str, k: int = config.TOP_K, **kw) -> list[dict]:
        return self.buscar_multi([pergunta], k, **kw)


class Buscador(_BuscaBase):
    """Busca nos artigos (índice criado por `python rag.py indexar`)."""

    def __init__(self):
        arq = config.PASTA_INDICE / "bm25.pkl"
        if not arq.exists():
            raise SystemExit("Índice não encontrado. Rode primeiro: python rag.py indexar")
        with open(arq, "rb") as f:
            dados = pickle.load(f)
        self.chunks = dados["chunks"]
        self._preparar(dados["tokens"])
        self.fontes = json.loads(config.ARQ_FONTES.read_text(encoding="utf-8"))
        self.vet = None
        emb_arq = config.PASTA_INDICE / "emb.npy"
        if emb_arq.exists() and _embedder():
            import numpy as np
            vet = np.load(emb_arq)
            if len(vet) == len(self.chunks):
                self.vet = vet


class BuscadorMemoria(_BuscaBase):
    """Índice montado na hora (usado para os READMEs de contexto, que são poucos)."""

    def __init__(self, chunks: list[dict]):
        self.chunks = chunks
        # BM25Plus: no Okapi, com poucos documentos o IDF zera e nada é encontrado
        self._preparar([tokenizar(c["texto"]) for c in chunks], BM25Plus)
        self.vet = _vetorizar([c["texto"] for c in chunks])

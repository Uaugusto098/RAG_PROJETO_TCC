"""
Índice e busca híbrida:
  - BM25 (palavras-chave, funciona sempre, offline)
  - Embeddings multilíngues (opcional: pip install sentence-transformers)
Os dois rankings são combinados por Reciprocal Rank Fusion.
"""
from __future__ import annotations

import json
import pickle
import re
import unicodedata

from rank_bm25 import BM25Okapi

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


# ------------------------------------------------------------ índice
def construir(chunks: list[dict]) -> None:
    config.PASTA_INDICE.mkdir(exist_ok=True)
    tokens = [tokenizar(c["texto"]) for c in chunks]
    with open(config.PASTA_INDICE / "bm25.pkl", "wb") as f:
        pickle.dump({"chunks": chunks, "tokens": tokens}, f)

    emb = _embedder()
    if emb:
        import numpy as np
        vet = emb.encode(["passage: " + c["texto"] for c in chunks],
                         normalize_embeddings=True, show_progress_bar=True)
        np.save(config.PASTA_INDICE / "emb.npy", vet)
        print(f"  índice semântico: {len(chunks)} trechos")
    else:
        (config.PASTA_INDICE / "emb.npy").unlink(missing_ok=True)
        print("  índice só por palavras-chave (instale sentence-transformers para busca semântica)")
    print(f"  índice BM25: {len(chunks)} trechos")


class Buscador:
    def __init__(self):
        arq = config.PASTA_INDICE / "bm25.pkl"
        if not arq.exists():
            raise SystemExit("Índice não encontrado. Rode primeiro: python rag.py indexar")
        with open(arq, "rb") as f:
            dados = pickle.load(f)
        self.chunks = dados["chunks"]
        self.bm25 = BM25Okapi(dados["tokens"])
        self.fontes = json.loads(config.ARQ_FONTES.read_text(encoding="utf-8"))
        self.vet = None
        emb_arq = config.PASTA_INDICE / "emb.npy"
        if emb_arq.exists() and _embedder():
            import numpy as np
            self.vet = np.load(emb_arq)

    def buscar(self, pergunta: str, k: int = config.TOP_K) -> list[dict]:
        rankings = []
        notas = self.bm25.get_scores(tokenizar(pergunta))
        rankings.append(sorted(range(len(notas)), key=lambda i: -notas[i])[:50])

        if self.vet is not None:
            q = _embedder().encode(["query: " + pergunta], normalize_embeddings=True)[0]
            sims = self.vet @ q
            rankings.append(list(sims.argsort()[::-1][:50]))

        # Reciprocal Rank Fusion
        fusao: dict[int, float] = {}
        for r in rankings:
            for pos, i in enumerate(r):
                fusao[int(i)] = fusao.get(int(i), 0) + 1 / (60 + pos)
        melhores = sorted(fusao, key=lambda i: -fusao[i])
        if len(rankings) == 1:  # só BM25: descarta trechos sem nenhum termo em comum
            melhores = [i for i in melhores if notas[i] > 0]
        return [self.chunks[i] for i in melhores[:k]]

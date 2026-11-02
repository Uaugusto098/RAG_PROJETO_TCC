"""
Ingestão: lê os PDFs, extrai texto página a página, gera os trechos (chunks)
e cria/atualiza fontes.json com um rascunho dos metadados ABNT.

Os metadados automáticos são só um ponto de partida: abra fontes.json e
confira autores, título, periódico, volume, páginas e "primeira_pagina".
"""
from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

import pymupdf

import config

RE_DOI = re.compile(r"\b(10\.\d{4,9}/[^\s\"<>,;]+)", re.I)
RE_ANO = re.compile(r"\b(19[5-9]\d|20[0-4]\d)\b")


# ------------------------------------------------------------ utilidades
def slug(texto: str) -> str:
    t = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "_", t.lower()).strip("_")[:40] or "fonte"


def limpar(texto: str) -> str:
    texto = texto.replace("­", "")                       # hífen invisível
    texto = re.sub(r"(\w)-\n(\w)", r"\1\2", texto)            # hifenização de quebra
    texto = re.sub(r"[ \t]+", " ", texto)
    texto = re.sub(r"\n{3,}", "\n\n", texto)
    return texto.strip()


# ------------------------------------------------------------ extração
def extrair_paginas(pdf: Path) -> list[str]:
    with pymupdf.open(pdf) as doc:
        return [limpar(p.get_text("text")) for p in doc]


def rascunho_metadados(pdf: Path, paginas: list[str]) -> dict:
    """Palpite inicial de metadados a partir do PDF. SEMPRE revisar."""
    with pymupdf.open(pdf) as doc:
        meta = doc.metadata or {}
    inicio = "\n".join(paginas[:2])

    autores = []
    for nome in re.split(r"[;,&]| and | e ", meta.get("author") or ""):
        partes = nome.strip().split()
        if len(partes) >= 2:
            autores.append({"sobrenome": partes[-1], "nome": " ".join(partes[:-1])})

    doi = RE_DOI.search(inicio)
    ano = RE_ANO.search(meta.get("creationDate", "") or "") or RE_ANO.search(inicio)
    titulo = (meta.get("title") or "").strip()
    if not titulo:
        linhas = [l.strip() for l in paginas[0].splitlines() if len(l.strip()) > 15] if paginas else []
        titulo = linhas[0] if linhas else pdf.stem

    return {
        "arquivo": pdf.name,
        "revisado": False,
        "tipo": "artigo",
        "autores": autores,
        "titulo": titulo,
        "subtitulo": "",
        "periodico": "",
        "local": "",
        "volume": "",
        "numero": "",
        "paginas": "",
        "mes": "",
        "ano": ano.group(1) if ano else "",
        "doi": doi.group(1).rstrip(".") if doi else "",
        "url": "",
        "acesso": "",
        "primeira_pagina": 1,
    }


# ------------------------------------------------------------ fontes.json
def carregar_fontes() -> dict:
    if config.ARQ_FONTES.exists():
        return json.loads(config.ARQ_FONTES.read_text(encoding="utf-8"))
    return {}


def salvar_fontes(fontes: dict) -> None:
    config.ARQ_FONTES.write_text(json.dumps(fontes, ensure_ascii=False, indent=2),
                                 encoding="utf-8")


def pagina_impressa(fonte: dict, pagina_pdf: int) -> int:
    """Converte a página do arquivo PDF na página impressa do artigo.

    Ex.: artigo nas p. 45-60 da revista -> primeira_pagina = 45,
    então a página 3 do PDF vira p. 47 na citação.
    """
    try:
        inicio = int(fonte.get("primeira_pagina") or 1)
    except ValueError:
        inicio = 1
    return inicio + pagina_pdf - 1


# ------------------------------------------------------------ chunks
def fatiar(texto: str, tam: int, sobrep: int) -> list[str]:
    if len(texto) <= tam:
        return [texto] if texto.strip() else []
    paragrafos = re.split(r"\n\s*\n|(?<=[.!?])\s+", texto)
    trechos, atual = [], ""
    for p in paragrafos:
        if len(atual) + len(p) + 1 > tam and atual:
            trechos.append(atual.strip())
            atual = atual[-sobrep:] + " " + p
        else:
            atual += " " + p
    if atual.strip():
        trechos.append(atual.strip())
    return trechos


def ingerir(pasta: Path | None = None) -> tuple[list[dict], dict]:
    pasta = pasta or config.PASTA_ARTIGOS
    fontes = carregar_fontes()
    por_arquivo = {f["arquivo"]: fid for fid, f in fontes.items()}
    chunks: list[dict] = []

    pdfs = sorted(pasta.glob("*.pdf"))
    if not pdfs:
        raise SystemExit(f"Nenhum PDF encontrado em {pasta}")

    for pdf in pdfs:
        paginas = extrair_paginas(pdf)
        if paginas and sum(len(p) for p in paginas) / len(paginas) < 40:
            print(f"  ! {pdf.name}: quase sem texto (PDF escaneado?). Rode OCR antes.")
        fid = por_arquivo.get(pdf.name)
        if fid is None:  # PDF novo: cria rascunho de metadados
            meta = rascunho_metadados(pdf, paginas)
            base = slug((meta["autores"][0]["sobrenome"] if meta["autores"] else pdf.stem)
                        + meta["ano"])
            fid, n = base, 2
            while fid in fontes:
                fid, n = f"{base}_{n}", n + 1
            fontes[fid] = meta
            print(f"  + {pdf.name} -> '{fid}' (revise os metadados em fontes.json)")

        for i, texto in enumerate(paginas, start=1):
            for j, t in enumerate(fatiar(texto, config.TAM_CHUNK, config.SOBREPOSICAO)):
                chunks.append({"fonte": fid, "pagina_pdf": i, "ordem": j, "texto": t})

    salvar_fontes(fontes)
    return chunks, fontes

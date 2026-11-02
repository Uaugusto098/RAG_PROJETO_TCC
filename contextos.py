"""
Contextos do autor: READMEs/resumos com a SUA ideia sobre os artigos.

Coloque arquivos .md, .txt ou .docx em contextos/. Eles NÃO são fontes citáveis:
servem para dizer ao Claude como você quer usar cada artigo, que argumento quer
construir, como as ideias se ligam ao seu tema. O Claude usa isso para escolher e
articular os trechos dos artigos (estes sim citados com página).

Cabeçalho opcional (frontmatter) no topo do arquivo:

    ---
    artigos: almeida2021, komagata2019      # ids do fontes.json ou nomes dos PDFs
    secoes: Fundamentação teórica, Introdução
    sempre: nao                              # sim = vai inteiro em toda chamada
    ---

- `artigos`: os artigos de que esse resumo fala. Quando o resumo for relevante, os
  trechos desses artigos são puxados junto. Também funciona sem cabeçalho: se o nome
  do arquivo for igual ao do PDF (ex.: almeida2021.md / almeida2021.pdf) ou se o id
  da fonte aparecer no texto, a ligação é feita sozinha.
- `secoes`: ao escrever essas seções, o README vai inteiro para o Claude.
- Arquivos que começam com "_" são ignorados (use para modelos/rascunhos).
- Comentários <!-- ... --> são ignorados.

Editou um README? Não precisa reindexar: eles são lidos a cada execução.
"""
from __future__ import annotations

import re
import unicodedata
from pathlib import Path

import config

EXTENSOES = (".md", ".markdown", ".txt", ".docx")


def normalizar(texto: str) -> str:
    t = unicodedata.normalize("NFKD", texto.lower()).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9.]+", " ", t)).strip()


def _sim(valor: str) -> bool:
    return normalizar(valor) in ("sim", "s", "true", "yes", "1", "verdadeiro")


# ------------------------------------------------------------ leitura
def _ler_texto(arq: Path) -> str:
    if arq.suffix.lower() == ".docx":
        from docx import Document
        return "\n\n".join(p.text for p in Document(arq).paragraphs if p.text.strip())
    return arq.read_text(encoding="utf-8", errors="replace")


def _frontmatter(texto: str) -> tuple[dict, str]:
    """Lê o cabeçalho '--- chave: valor ---' (listas por vírgula ou '- item')."""
    m = re.match(r"﻿?\s*---\s*\n(.*?)\n---\s*\n?", texto, re.S)
    if not m:
        return {}, texto
    meta, chave = {}, None
    for linha in m.group(1).splitlines():
        linha = re.sub(r"\s+#.*$", "", linha).rstrip()
        if not linha.strip():
            continue
        item = re.match(r"\s*-\s+(.*)", linha)
        if item and chave:
            meta.setdefault(chave, []).append(item.group(1).strip().strip("\"'"))
            continue
        kv = re.match(r"\s*([\w_]+)\s*:\s*(.*)", linha)
        if kv:
            chave = normalizar(kv.group(1)).replace(" ", "_")
            valor = kv.group(2).strip().strip("[]")
            meta[chave] = [v.strip().strip("\"'") for v in valor.split(",") if v.strip()]
    return meta, texto[m.end():]


def _resolver_artigos(nomes: list[str], fontes: dict) -> tuple[list[str], list[str]]:
    """Converte ids/nomes de arquivo em ids do fontes.json."""
    indice = {}
    for fid, f in fontes.items():
        arq = f.get("arquivo", "")
        for chave in (fid, arq, Path(arq).stem):
            if chave:
                indice[chave.lower()] = fid
    achados, faltando = [], []
    for nome in nomes:
        fid = indice.get(nome.lower()) or indice.get(Path(nome).stem.lower())
        if fid:
            if fid not in achados:
                achados.append(fid)
        else:
            faltando.append(nome)
    return achados, faltando


def carregar(fontes: dict | None = None) -> list[dict]:
    """Lista de contextos: {id, arquivo, titulo, texto, artigos, secoes, sempre, faltando}."""
    if fontes is None:
        import ingestao
        fontes = ingestao.carregar_fontes()
    pasta = config.PASTA_CONTEXTOS
    if not pasta.exists():
        return []
    ideia = config.ARQ_IDEIA_CENTRAL.resolve()
    saida = []
    for arq in sorted(pasta.rglob("*")):
        if (not arq.is_file() or arq.suffix.lower() not in EXTENSOES
                or arq.name.startswith((".", "_", "~$")) or arq.resolve() == ideia):
            continue
        meta, corpo = _frontmatter(_ler_texto(arq))
        corpo = re.sub(r"<!--.*?-->", "", corpo, flags=re.S).strip()
        if not corpo:
            continue
        nomes = list(meta.get("artigos", []))
        nomes.append(arq.stem)  # README com o mesmo nome do PDF/id
        nomes += [fid for fid in fontes if re.search(rf"\b{re.escape(fid)}\b", corpo)]
        artigos, faltando = _resolver_artigos(nomes, fontes)
        faltando = [n for n in faltando if n != arq.stem]
        titulo = next((l.lstrip("# ").strip() for l in corpo.splitlines()
                       if l.strip().startswith("#")), arq.stem)
        saida.append({
            "id": str(arq.relative_to(pasta)),
            "arquivo": arq.name,
            "titulo": titulo,
            "texto": corpo,
            "artigos": artigos,
            "faltando": faltando,
            "secoes": meta.get("secoes", []),
            "sempre": any(_sim(v) for v in meta.get("sempre", [])),
        })
    return saida


def ideia_central() -> str:
    arq = config.ARQ_IDEIA_CENTRAL
    if not arq.exists():
        return ""
    _, corpo = _frontmatter(_ler_texto(arq))
    corpo = re.sub(r"<!--.*?-->", "", corpo, flags=re.S).strip()
    # só títulos (modelo ainda não preenchido) -> vazio
    if not any(l.strip() and not l.strip().startswith("#") for l in corpo.splitlines()):
        return ""
    return corpo


# ------------------------------------------------------------ seleção
def para_secao(contexto: dict, titulo_secao: str) -> bool:
    alvo = normalizar(titulo_secao)
    alvo = re.sub(r"^[\d.]+\s*", "", alvo)
    for s in contexto["secoes"]:
        s = re.sub(r"^[\d.]+\s*", "", normalizar(s))
        if s and (s in alvo or alvo in s):
            return True
    return False


def chunks(contextos: list[dict]) -> list[dict]:
    """Fatia cada README (por título/parágrafo) para a busca."""
    from ingestao import fatiar
    saida = []
    for ctx in contextos:
        blocos = re.split(r"\n(?=#{1,6}\s)", ctx["texto"])
        ordem = 0
        for bloco in blocos:
            for t in fatiar(bloco.strip(), config.TAM_CHUNK, config.SOBREPOSICAO):
                saida.append({"tipo": "contexto", "fonte": ctx["id"], "ordem": ordem,
                              "texto": f"[{ctx['titulo']}]\n{t}", "artigos": ctx["artigos"]})
                ordem += 1
    return saida

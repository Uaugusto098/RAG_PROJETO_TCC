"""
Modelo da monografia (arquivo Word) e exportação das seções geradas.

- Lê o .docx de monografia/ e identifica os títulos (estilos "Título 1/2/3" ou
  "Heading 1/2/3"; se o documento não usar estilos, reconhece títulos numerados
  em MAIÚSCULAS/negrito, como "2 FUNDAMENTAÇÃO TEÓRICA").
- O texto que estiver embaixo de cada título (seu rascunho ou as orientações do
  modelo da instituição) é enviado ao Claude ao escrever aquela seção.
- Sem .docx, usa a estrutura padrão de monografia (NBR 14724).
- Converte as seções geradas (markdown) em .docx com formatação ABNT.
"""
from __future__ import annotations

import re
from pathlib import Path

import config
from contextos import normalizar

# ------------------------------------------------------------ estrutura padrão
ESTRUTURA_PADRAO = [
    (1, "", "RESUMO"),
    (1, "1", "INTRODUÇÃO"),
    (1, "2", "FUNDAMENTAÇÃO TEÓRICA"),
    (1, "3", "METODOLOGIA"),
    (1, "4", "RESULTADOS E DISCUSSÃO"),
    (1, "5", "CONSIDERAÇÕES FINAIS"),
]

# Títulos sem número que contam como seção (pré e pós-textuais, NBR 14724)
TITULOS_FIXOS = {
    "resumo", "abstract", "resumen", "introducao", "conclusao", "conclusoes",
    "consideracoes finais", "referencias", "apendice", "anexo", "agradecimentos",
    "dedicatoria", "epigrafe", "sumario", "glossario",
}

# Títulos que não são seções a escrever (o conteúdo embaixo deles é ignorado)
NAO_SECOES = {"sumario", "referencias", "referencias bibliograficas", "indice"}

# Orientações por tipo de seção (NBR 14724 / práticas usuais de TCC)
ORIENTACOES = {
    "resumo": (
        "Resumo (NBR 6028:2021): parágrafo único, voz ativa, 3ª pessoa, de 150 a 500 "
        "palavras, com objetivo, método, resultados e conclusões. Sem citações. Ao final, "
        "linha 'Palavras-chave:' com 3 a 5 termos separados por ponto e vírgula."),
    "abstract": (
        "Abstract: versão fiel do resumo em inglês acadêmico, parágrafo único, seguida "
        "de 'Keywords:'. Sem citações."),
    "introducao": (
        "Introdução: contextualize o tema a partir da literatura (com citações), "
        "delimite o tema, apresente o problema de pesquisa (pergunta), o objetivo geral e "
        "os objetivos específicos (verbos no infinitivo), a justificativa (relevância "
        "acadêmica, social e prática) e, ao final, um parágrafo que descreve a estrutura "
        "do trabalho (o que cada capítulo apresenta)."),
    "fundamentacao": (
        "Fundamentação teórica / referencial teórico: organize em subseções temáticas "
        "(siga os subtítulos do modelo, se houver). Defina conceitos, apresente as visões "
        "dos autores, compare, aproxime e contraponha os autores entre si e conecte "
        "explicitamente cada bloco ao problema da pesquisa. É a seção com maior densidade "
        "de citações: praticamente todo parágrafo deve ter fonte."),
    "metodologia": (
        "Metodologia: caracterize a pesquisa (natureza, abordagem qualitativa/quantitativa, "
        "objetivos exploratória/descritiva/explicativa, procedimentos: bibliográfica, "
        "estudo de caso, survey etc.), descreva universo/amostra ou corpus, instrumentos e "
        "procedimentos de coleta, e a técnica de análise. Justifique as escolhas com "
        "autores de metodologia quando houver nos trechos. Use o que está no rascunho "
        "e nos contextos do autor; não invente procedimentos que o autor não descreveu: "
        "marque [COMPLETAR: ...] onde faltar informação."),
    "resultados": (
        "Resultados e discussão: apresente os achados descritos pelo autor (rascunho e "
        "contextos) e discuta-os à luz da literatura, mostrando convergências e "
        "divergências com os autores citados. Não invente dados: marque [COMPLETAR: ...] "
        "onde faltarem resultados."),
    "consideracoes": (
        "Considerações finais / conclusão: retome o problema e o objetivo geral, mostre "
        "como cada objetivo específico foi atendido, sintetize as principais contribuições, "
        "aponte limitações e sugira trabalhos futuros. Não traga informação nova nem "
        "citações longas."),
}

CHAVES_TIPO = [
    ("abstract", ("abstract",)),
    ("resumo", ("resumo",)),
    ("introducao", ("introducao",)),
    ("fundamentacao", ("fundamentacao", "referencial", "revisao", "marco teorico",
                       "estado da arte", "teoric")),
    ("metodologia", ("metodolog", "metodo", "procedimentos", "materiais")),
    ("resultados", ("resultado", "discuss", "analise")),
    ("consideracoes", ("consideracoes finais", "conclus")),
]


def tipo_secao(titulo: str) -> str:
    t = normalizar(titulo)
    for tipo, chaves in CHAVES_TIPO:
        if any(c in t for c in chaves):
            return tipo
    return "padrao"


def orientacao(titulo: str) -> str:
    return ORIENTACOES.get(tipo_secao(titulo),
                           "Desenvolva a seção de forma coerente com o problema e os objetivos "
                           "da pesquisa, fundamentando as afirmações nos trechos dos artigos.")


# ------------------------------------------------------------ leitura do .docx
def arquivo_modelo() -> Path | None:
    pasta = config.PASTA_MONOGRAFIA
    if config.ARQUIVO_MONOGRAFIA:
        arq = pasta / config.ARQUIVO_MONOGRAFIA
        return arq if arq.exists() else None
    docs = [p for p in pasta.glob("*.docx") if not p.name.startswith(("~$", "."))] \
        if pasta.exists() else []
    return max(docs, key=lambda p: p.stat().st_mtime) if docs else None


RE_NUMERADO = re.compile(r"^(\d+(?:\.\d+)*)\.?\s+(\S.{0,150})$")
RE_SUMARIO = re.compile(r"(\.{4,}|…{2,}|\t)\s*\d+\s*$")


def _nivel_por_estilo(par) -> int:
    estilo = par.style
    while estilo is not None:
        nome = (estilo.name or "").lower()
        if nome.startswith(("toc", "sumário", "sumario", "índice", "indice")):
            return 0
        m = re.match(r"(heading|t[ií]tulo)\s*(\d)", nome)
        if m:
            return int(m.group(2))
        lvl = estilo.element.xpath("./w:pPr/w:outlineLvl/@w:val")
        if lvl and lvl[0].isdigit() and int(lvl[0]) < 9:
            return int(lvl[0]) + 1
        estilo = estilo.base_style
    lvl = par._p.xpath("./w:pPr/w:outlineLvl/@w:val")
    if lvl and lvl[0].isdigit() and int(lvl[0]) < 9:
        return int(lvl[0]) + 1
    return 0


def _parece_titulo(par, texto: str) -> int:
    """Fallback para documentos sem estilos de título."""
    if len(texto) > 150 or RE_SUMARIO.search(texto) or texto.endswith((".", ":", ";", ",")):
        return 0
    negrito = bool(par.runs) and all(r.bold for r in par.runs if r.text.strip())
    maiusc = texto == texto.upper() and any(c.isalpha() for c in texto)
    m = RE_NUMERADO.match(texto)
    if m and (maiusc or negrito):
        return m.group(1).count(".") + 1
    n = normalizar(texto)
    if (maiusc or negrito) and (n in TITULOS_FIXOS or n == "referencias bibliograficas"
                                or n.startswith(("apendice ", "anexo "))):
        return 1
    return 0


def ler_estrutura(arq: Path | None = None) -> list[dict]:
    """Seções do modelo: [{nivel, numero, titulo, paragrafos}] (na ordem do documento)."""
    arq = arq or arquivo_modelo()
    if arq is None:
        return ler_estrutura_padrao()
    from docx import Document
    doc = Document(arq)
    pars = [(p, p.text.strip()) for p in doc.paragraphs]
    usa_estilos = any(_nivel_por_estilo(p) for p, t in pars if t)

    secoes, atual, em_sumario = [], None, False
    for p, texto in pars:
        if not texto:
            continue
        nivel = _nivel_por_estilo(p) if usa_estilos else _parece_titulo(p, texto)
        if nivel and RE_SUMARIO.search(texto):
            nivel = 0
        if nivel:
            n = normalizar(re.sub(r"^\d+(\.\d+)*\.?\s+", "", texto))
            if n in NAO_SECOES or n.startswith("lista de"):
                em_sumario, atual = True, None  # sumário, listas e referências: ignora
                continue
            em_sumario = False
            m = RE_NUMERADO.match(texto)
            numero, titulo = (m.group(1), m.group(2).strip()) if m else ("", texto)
            atual = {"nivel": nivel, "numero": numero, "titulo": titulo, "paragrafos": []}
            secoes.append(atual)
        elif atual is not None and not em_sumario:
            atual["paragrafos"].append(texto)
    if not secoes:
        print(f"  ! Não encontrei títulos em {arq.name}; usando a estrutura padrão. "
              "Dica: formate os títulos com os estilos 'Título 1', 'Título 2'...")
        return ler_estrutura_padrao()
    return secoes


def ler_estrutura_padrao() -> list[dict]:
    return [{"nivel": n, "numero": num, "titulo": t, "paragrafos": [], "padrao": True}
            for n, num, t in ESTRUTURA_PADRAO]


def rotulo(s: dict) -> str:
    return f"{s['numero']} {s['titulo']}".strip()


def sumario(secoes: list[dict]) -> str:
    return "\n".join("  " * (s["nivel"] - 1) + rotulo(s) for s in secoes)


def localizar(secoes: list[dict], alvo: str) -> int | None:
    """Acha a seção por número ('2.1'), posição ('#3') ou parte do título."""
    alvo = alvo.strip()
    if alvo.startswith("#") and alvo[1:].isdigit():
        i = int(alvo[1:]) - 1
        return i if 0 <= i < len(secoes) else None
    for i, s in enumerate(secoes):
        if s["numero"] and s["numero"] == alvo.rstrip("."):
            return i
    n = normalizar(re.sub(r"^\d+(\.\d+)*\.?\s+", "", alvo))
    for i, s in enumerate(secoes):  # título exato
        if normalizar(s["titulo"]) == n:
            return i
    for i, s in enumerate(secoes):  # parte do título
        if n and n in normalizar(s["titulo"]):
            return i
    return None


def subarvore(secoes: list[dict], i: int) -> list[dict]:
    """A seção i e todas as suas subseções."""
    saida = [secoes[i]]
    for s in secoes[i + 1:]:
        if s["nivel"] <= secoes[i]["nivel"]:
            break
        saida.append(s)
    return saida


def ancestrais(secoes: list[dict], i: int) -> list[dict]:
    """Seções-mãe de i, da mais externa para a mais interna."""
    saida, nivel = [], secoes[i]["nivel"]
    for s in reversed(secoes[:i]):
        if s["nivel"] < nivel:
            saida.insert(0, s)
            nivel = s["nivel"]
    return saida


def texto_secoes(secoes: list[dict]) -> str:
    partes = []
    for s in secoes:
        partes.append("#" * s["nivel"] + " " + rotulo(s))
        partes += s["paragrafos"]
    return "\n\n".join(partes)


# ------------------------------------------------------------ seções geradas
def slug(texto: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", normalizar(texto)).strip("_")[:50] or "secao"


def arquivo_secao(i: int, s: dict) -> Path:
    return config.PASTA_SECOES / f"{i + 1:02d}_{slug(rotulo(s))}.md"


MARCA_RODAPE = "<!-- rodape -->"


def secoes_geradas() -> list[tuple[Path, str]]:
    """[(arquivo, corpo sem rodapé)] em ordem."""
    if not config.PASTA_SECOES.exists():
        return []
    saida = []
    for arq in sorted(config.PASTA_SECOES.glob("*.md")):
        corpo = arq.read_text(encoding="utf-8").split(MARCA_RODAPE)[0].strip()
        saida.append((arq, corpo))
    return saida


# ------------------------------------------------------------ markdown -> docx
def _doc_base(usar_modelo: bool):
    from docx import Document
    from docx.shared import Cm, Pt
    modelo = arquivo_modelo() if usar_modelo else None
    if modelo:
        doc = Document(modelo)
        corpo = doc.element.body
        for filho in list(corpo):
            if not filho.tag.endswith("}sectPr"):
                corpo.remove(filho)
        return doc
    doc = Document()
    normal = doc.styles["Normal"]
    normal.font.name = "Times New Roman"
    normal.font.size = Pt(12)
    for sec in doc.sections:  # NBR 14724: 3 cm sup./esq., 2 cm inf./dir.
        sec.top_margin = sec.left_margin = Cm(3)
        sec.bottom_margin = sec.right_margin = Cm(2)
    return doc


def _runs(par, texto: str):
    """Aplica **negrito** e *itálico* do markdown."""
    for parte in re.split(r"(\*\*[^*]+\*\*|\*[^*\s][^*]*\*)", texto):
        if not parte:
            continue
        if parte.startswith("**") and parte.endswith("**"):
            par.add_run(parte[2:-2]).bold = True
        elif parte.startswith("*") and parte.endswith("*") and len(parte) > 2:
            par.add_run(parte[1:-1]).italic = True
        else:
            par.add_run(parte)


def _paragrafo(doc, texto: str, tipo: str = "corpo"):
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.shared import Cm, Pt
    par = doc.add_paragraph()
    fmt = par.paragraph_format
    if tipo == "citacao":  # citação direta longa: recuo 4 cm, fonte menor, espaço simples
        fmt.left_indent = Cm(4)
        fmt.line_spacing = 1.0
        fmt.space_after = Pt(12)
        fmt.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        _runs(par, texto)
        for r in par.runs:
            r.font.size = Pt(10)
        return par
    if tipo == "referencia":  # NBR 6023: alinhada à esquerda, espaço simples
        fmt.alignment = WD_ALIGN_PARAGRAPH.LEFT
        fmt.line_spacing = 1.0
        fmt.space_after = Pt(12)
    elif tipo == "lista":
        fmt.left_indent = Cm(1.25)
        fmt.line_spacing = 1.5
        fmt.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        texto = "• " + texto
    else:
        fmt.first_line_indent = Cm(1.25)
        fmt.line_spacing = 1.5
        fmt.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    _runs(par, texto)
    return par


def _titulo(doc, texto: str, nivel: int):
    from docx.shared import Pt
    try:
        h = doc.add_heading(level=min(max(nivel, 1), 9))
        h.add_run(texto)
        return h
    except KeyError:  # modelo sem o estilo de título
        par = doc.add_paragraph()
        run = par.add_run(texto.upper() if nivel == 1 else texto)
        run.bold = True
        run.font.size = Pt(12)
        return par


def markdown_para_docx(doc, md: str, referencias: bool = False):
    blocos = re.split(r"\n\s*\n", md.strip())
    for bloco in blocos:
        linhas = [l.rstrip() for l in bloco.strip().splitlines() if l.strip()]
        if not linhas:
            continue
        m = re.match(r"^(#{1,6})\s+(.*)", linhas[0])
        if m:
            _titulo(doc, m.group(2).strip(), len(m.group(1)))
            linhas = linhas[1:]
            if not linhas:
                continue
        if all(l.lstrip().startswith(">") for l in linhas):
            _paragrafo(doc, " ".join(l.lstrip()[1:].strip() for l in linhas), "citacao")
        elif all(re.match(r"\s*([-*•]|\d+[.)])\s+", l) for l in linhas):
            for l in linhas:
                _paragrafo(doc, re.sub(r"^\s*([-*•]|\d+[.)])\s+", "", l), "lista")
        else:
            _paragrafo(doc, " ".join(l.strip() for l in linhas),
                       "referencia" if referencias else "corpo")


def salvar_docx(md: str, refs: str, destino: Path, usar_modelo: bool = True):
    doc = _doc_base(usar_modelo)
    markdown_para_docx(doc, md)
    if refs:
        _titulo(doc, "REFERÊNCIAS", 1)
        markdown_para_docx(doc, refs, referencias=True)
    destino.parent.mkdir(parents=True, exist_ok=True)
    doc.save(destino)
    return destino

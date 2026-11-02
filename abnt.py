"""
Formatação ABNT.

- Citações no texto: NBR 10520:2023
  (Silva, 2020, p. 15) | (Silva; Souza, 2020, p. 15) | (Silva et al., 2020, p. 15)
  Opção CITACAO_MAIUSCULA=True gera o formato antigo (SILVA, 2020, p. 15),
  ainda exigido por muitas instituições.

- Referências: NBR 6023:2018
  Artigo, livro, capítulo, tese/dissertação/TCC, anais de evento e página web.
"""
from __future__ import annotations

import config

MESES = ["jan.", "fev.", "mar.", "abr.", "maio", "jun.",
         "jul.", "ago.", "set.", "out.", "nov.", "dez."]


# ----------------------------------------------------------------- autores
def _sobrenome_citacao(autor: dict) -> str:
    s = autor.get("sobrenome", "").strip()
    return s.upper() if config.CITACAO_MAIUSCULA else s


def autores_citacao(fonte: dict) -> str:
    autores = fonte.get("autores") or []
    if not autores:
        # Sem autor: entra pela primeira palavra do título (NBR 10520)
        primeira = (fonte.get("titulo") or "SEM TÍTULO").split()[0]
        return primeira.upper() + " ..."
    if len(autores) >= 4:
        return f"{_sobrenome_citacao(autores[0])} et al."
    return "; ".join(_sobrenome_citacao(a) for a in autores)


def autores_referencia(fonte: dict) -> str:
    autores = fonte.get("autores") or []
    if not autores:
        return ""

    def um(a):
        nome = a.get("nome", "").strip()
        sob = a.get("sobrenome", "").strip().upper()
        return f"{sob}, {nome}" if nome else sob

    if len(autores) >= 4 and config.REFERENCIA_ET_AL:
        return f"{um(autores[0])} et al."
    return "; ".join(um(a) for a in autores)


# ----------------------------------------------------------------- citação
def citacao(fonte: dict, pagina: int | str | None = None) -> str:
    """Citação de autor-data entre parênteses, com página quando houver."""
    partes = [autores_citacao(fonte), str(fonte.get("ano") or "[s. d.]")]
    if pagina not in (None, ""):
        partes.append(f"p. {pagina}")
    return "(" + ", ".join(partes) + ")"


# -------------------------------------------------------------- referência
def _b(txt: str) -> str:
    """Destaque em negrito (markdown)."""
    return f"**{txt}**" if txt else ""


def _titulo(fonte: dict, destacar: bool) -> str:
    t = (fonte.get("titulo") or "").strip().rstrip(".")
    sub = (fonte.get("subtitulo") or "").strip().rstrip(".")
    if destacar:
        return f"{_b(t)}: {sub}" if sub else _b(t)
    return f"{t}: {sub}" if sub else t


def _online(fonte: dict) -> str:
    out = ""
    if fonte.get("doi"):
        out += f" DOI: {fonte['doi']}."
    if fonte.get("url"):
        out += f" Disponível em: {fonte['url']}."
        if fonte.get("acesso"):
            out += f" Acesso em: {fonte['acesso']}."
    return out


def _data(fonte: dict) -> str:
    mes = fonte.get("mes")
    ano = fonte.get("ano") or "[s. d.]"
    if mes:
        try:
            mes = MESES[int(mes) - 1]
        except (ValueError, IndexError):
            pass
        return f"{mes} {ano}"
    return str(ano)


def referencia(fonte: dict) -> str:
    tipo = (fonte.get("tipo") or "artigo").lower()
    aut = autores_referencia(fonte)
    local = fonte.get("local") or "[S. l.]"
    editora = fonte.get("editora") or "[s. n.]"
    ano = fonte.get("ano") or "[s. d.]"
    ed = f" {fonte['edicao']}. ed." if fonte.get("edicao") else ""

    if tipo == "livro":
        ref = f"{aut}. {_titulo(fonte, True)}.{ed} {local}: {editora}, {ano}."

    elif tipo == "capitulo":
        org = fonte.get("organizadores", "")
        ref = (f"{aut}. {_titulo(fonte, False)}. In: {org}. "
               f"{_b(fonte.get('livro', ''))}.{ed} {local}: {editora}, {ano}.")
        if fonte.get("paginas"):
            ref = ref[:-1] + f". p. {fonte['paginas']}."

    elif tipo in ("tese", "dissertacao", "tcc"):
        grau = fonte.get("grau") or {
            "tese": "Tese (Doutorado)",
            "dissertacao": "Dissertação (Mestrado)",
            "tcc": "Trabalho de Conclusão de Curso (Graduação)"}[tipo]
        inst = fonte.get("instituicao", "")
        ref = f"{aut}. {_titulo(fonte, True)}. {ano}. {grau} – {inst}, {local}, {ano}."

    elif tipo == "evento":
        ref = (f"{aut}. {_titulo(fonte, False)}. In: {fonte.get('evento', '')}, "
               f"{fonte.get('edicao_evento', '')}, {ano}, {fonte.get('local_evento', local)}. "
               f"{_b(fonte.get('anais', 'Anais'))} [...]. {local}: {editora}, {ano}.")
        if fonte.get("paginas"):
            ref = ref[:-1] + f". p. {fonte['paginas']}."

    elif tipo == "web":
        ref = f"{aut + '. ' if aut else ''}{_titulo(fonte, True)}. {local}, {_data(fonte)}."

    else:  # artigo de periódico
        partes = [_b(fonte.get("periodico", "")), local]
        if fonte.get("volume"):
            partes.append(f"v. {fonte['volume']}")
        if fonte.get("numero"):
            partes.append(f"n. {fonte['numero']}")
        if fonte.get("paginas"):
            partes.append(f"p. {fonte['paginas']}")
        partes.append(_data(fonte))
        ref = f"{aut}. {_titulo(fonte, False)}. " + ", ".join(p for p in partes if p) + "."

    # Obra sem autor: título entra em maiúscula na primeira palavra
    if not aut:
        ref = ref.lstrip(". ")
    return (ref + _online(fonte)).replace("..", ".").replace(" .", ".")


def lista_referencias(fontes: list[dict]) -> str:
    """Lista em ordem alfabética, como exige a NBR 6023."""
    refs = sorted((referencia(f) for f in fontes),
                  key=lambda r: r.replace("*", "").lower())
    return "\n\n".join(refs)

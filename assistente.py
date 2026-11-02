"""
Monta o prompt com os trechos recuperados, chama o Claude e
anexa as REFERÊNCIAS em ABNT geradas pelo código (não pela LLM),
para que fiquem exatamente iguais aos metadados de fontes.json.
"""
from __future__ import annotations

import re
from collections import defaultdict

import abnt
import config
from ingestao import pagina_impressa

SISTEMA = """Você é o assistente de pesquisa de um Trabalho de Conclusão de Curso (TCC).
Responda SOMENTE com base nos trechos de artigos fornecidos em <trechos>.

Regras obrigatórias:
1. Toda afirmação tirada dos trechos termina com a citação ABNT exatamente como
   aparece no campo "citação" do trecho usado, ex.: (Silva, 2020, p. 47).
   Nunca invente autor, ano ou página. Várias fontes juntas: (Silva, 2020, p. 4; Souza, 2019, p. 7).
2. Citação direta curta (até 3 linhas) vai entre aspas duplas no corpo do texto, copiada
   literalmente do trecho, seguida da citação com página. Citação direta com mais de 3 linhas
   vai em parágrafo próprio, recuado (use "> " no início), sem aspas.
3. Prefira paráfrase (citação indireta) e escreva em português acadêmico, impessoal.
4. Se os trechos não bastarem para responder, diga claramente o que não foi encontrado
   nos artigos. Não complete com conhecimento próprio sem avisar; se usar, marque o
   parágrafo com [conhecimento geral – sem fonte nos artigos].
5. Não escreva a lista de referências: ela é gerada automaticamente depois da resposta.
"""


def preparar_fontes(fontes: dict) -> dict:
    """Mesma autoria + mesmo ano -> 2020a, 2020b (NBR 10520)."""
    grupos = defaultdict(list)
    for fid, f in fontes.items():
        grupos[(abnt.autores_citacao(f), str(f.get("ano")))].append(fid)
    fontes = {k: dict(v) for k, v in fontes.items()}
    for ids in grupos.values():
        if len(ids) > 1:
            for letra, fid in zip("abcdefghij", sorted(ids, key=lambda i: fontes[i].get("titulo", ""))):
                fontes[fid]["ano"] = f"{fontes[fid]['ano']}{letra}"
    return fontes


def montar_contexto(trechos: list[dict], fontes: dict) -> str:
    blocos = []
    for n, t in enumerate(trechos, 1):
        f = fontes[t["fonte"]]
        pag = pagina_impressa(f, t["pagina_pdf"])
        blocos.append(
            f'<trecho id="T{n}" fonte="{t["fonte"]}" arquivo="{f["arquivo"]}" '
            f'pagina_pdf="{t["pagina_pdf"]}">\n'
            f'citação: {abnt.citacao(f, pag)}\n'
            f'título: {f.get("titulo", "")}\n'
            f'{t["texto"]}\n</trecho>')
    return "<trechos>\n" + "\n\n".join(blocos) + "\n</trechos>"


def fontes_citadas(resposta: str, trechos: list[dict], fontes: dict) -> list[str]:
    usadas = []
    for t in trechos:
        f = fontes[t["fonte"]]
        chave = f"{abnt.autores_citacao(f)}, {f.get('ano')}"
        if chave in resposta and t["fonte"] not in usadas:
            usadas.append(t["fonte"])
    return usadas


def verificar_citacoes(resposta: str, trechos: list[dict], fontes: dict) -> list[str]:
    """Aponta citações na resposta que não correspondem a nenhum trecho recuperado."""
    validas = set()
    for t in trechos:
        f = fontes[t["fonte"]]
        validas.add((f"{abnt.autores_citacao(f)}, {f.get('ano')}",
                     str(pagina_impressa(f, t["pagina_pdf"]))))
    suspeitas = []
    # citações com página: "Silva; Souza, 2020, p. 47" (ou p. 47-48)
    for autor_ano, pag in re.findall(r"([^();]+?, \d{4}[a-z]?), p\. (\d+)", resposta):
        aa = autor_ano.strip()
        # coautores separados por ";" chegam só com o último sobrenome -> compara pelo final
        if not any(k.endswith(aa) and p == pag for k, p in validas):
            suspeitas.append(f"{aa}, p. {pag}")
    return suspeitas


def rodape(resposta: str, trechos: list[dict], fontes: dict) -> str:
    usadas = fontes_citadas(resposta, trechos, fontes)
    saida = ""
    alerta = verificar_citacoes(resposta, trechos, fontes)
    if alerta:
        saida += ("\n\n⚠ Citações não conferem com os trechos recuperados (verifique): "
                  + "; ".join(alerta))
    nao_rev = [fid for fid in usadas if not fontes[fid].get("revisado")]
    if nao_rev:
        saida += ("\n\n⚠ Metadados ainda não revisados em fontes.json: " + ", ".join(nao_rev))
    if usadas:
        saida += "\n\nREFERÊNCIAS\n\n" + abnt.lista_referencias([fontes[f] for f in usadas])
    return saida


class Assistente:
    def __init__(self, buscador):
        self.buscador = buscador
        self.fontes = preparar_fontes(buscador.fontes)
        self.historico: list[dict] = []
        self._cliente = None

    @property
    def cliente(self):
        if self._cliente is None:
            import anthropic
            self._cliente = anthropic.Anthropic()  # usa ANTHROPIC_API_KEY
        return self._cliente

    def recuperar(self, pergunta: str) -> list[dict]:
        consulta = pergunta
        if self.historico:  # perguntas de continuação herdam o assunto anterior
            consulta = self.historico[-2]["pergunta"] + " " + pergunta
        return self.buscador.buscar(consulta)

    def prompt_para_colar(self, pergunta: str) -> str:
        """Pacote pronto para colar numa conversa do Claude (sem API)."""
        trechos = self.recuperar(pergunta)
        refs = abnt.lista_referencias([self.fontes[f] for f in dict.fromkeys(t["fonte"] for t in trechos)])
        return (SISTEMA + "\n" + montar_contexto(trechos, self.fontes)
                + f"\n\nReferências ABNT das fontes acima (use ao final, só as citadas):\n\n{refs}"
                + f"\n\nPergunta: {pergunta}")

    def perguntar(self, pergunta: str) -> str:
        trechos = self.recuperar(pergunta)
        if not trechos:
            return "Não encontrei nada sobre isso nos artigos indexados."
        mensagens = [{"role": h["role"], "content": h["conteudo"]} for h in self.historico]
        mensagens.append({"role": "user", "content":
                          montar_contexto(trechos, self.fontes) + f"\n\nPergunta: {pergunta}"})

        resp = self.cliente.messages.create(
            model=config.MODELO_CLAUDE, max_tokens=config.MAX_TOKENS,
            system=SISTEMA, messages=mensagens)
        texto = "".join(b.text for b in resp.content if b.type == "text")

        # histórico guarda só pergunta/resposta (sem trechos) para não estourar contexto
        self.historico += [{"role": "user", "conteudo": pergunta, "pergunta": pergunta},
                           {"role": "assistant", "conteudo": texto}]
        return texto + rodape(texto, trechos, self.fontes)

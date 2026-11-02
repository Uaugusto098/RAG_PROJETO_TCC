"""
Monta o prompt com:
  - a IDEIA CENTRAL do TCC e os READMEs de contexto (sua visão sobre os artigos),
  - o modelo/rascunho da monografia (.docx),
  - os trechos recuperados dos artigos (únicas fontes citáveis),
chama o Claude e anexa as REFERÊNCIAS em ABNT geradas pelo código (não pela LLM),
para que fiquem exatamente iguais aos metadados de fontes.json.
"""
from __future__ import annotations

import re
from collections import defaultdict

import abnt
import config
import contextos
import monografia
from busca import BuscadorMemoria
from ingestao import pagina_impressa

REGRAS = """Regras obrigatórias:
1. Toda afirmação tirada dos trechos termina com a citação ABNT exatamente como
   aparece no campo "citação" do trecho usado, ex.: (Silva, 2020, p. 47).
   Na forma narrativa: Silva (2020, p. 47) afirma que...
   Nunca invente autor, ano ou página. Várias fontes juntas: (Silva, 2020, p. 4; Souza, 2019, p. 7).
2. Citação direta curta (até 3 linhas) vai entre aspas duplas no corpo do texto, copiada
   literalmente do trecho, seguida da citação com página. Citação direta com mais de 3 linhas
   vai em parágrafo próprio, recuado (use "> " no início), sem aspas.
3. Prefira paráfrase (citação indireta) e escreva em português acadêmico, impessoal.
4. Os textos em <ideia_central> e <contextos_do_autor> são do próprio autor do TCC: a ideia
   dele, seus resumos e interpretações dos artigos. Use-os para orientar o argumento, o
   recorte, a ordem das ideias e a escolha de quais artigos usar e como relacioná-los.
   Eles NÃO são fontes: nunca os cite. Quando um contexto atribuir uma ideia a um artigo,
   localize essa ideia nos <trechos> e cite o trecho. Se a ideia do autor não estiver apoiada
   em nenhum trecho, escreva-a como argumento do próprio trabalho (sem citação) ou marque
   [PRECISA DE FONTE] quando ela exigir respaldo da literatura.
5. Se os trechos não bastarem, diga claramente o que não foi encontrado nos artigos. Não
   complete com conhecimento próprio sem avisar; se usar, marque o parágrafo com
   [conhecimento geral – sem fonte nos artigos].
6. Não escreva a lista de referências: ela é gerada automaticamente depois da resposta.
"""

SISTEMA = ("Você é o assistente de pesquisa de um Trabalho de Conclusão de Curso (TCC).\n"
           "Responda com base nos trechos de artigos fornecidos em <trechos>, orientado pela "
           "ideia do autor.\n\n" + REGRAS)

SISTEMA_SECAO = (
    "Você é coautor acadêmico de uma monografia (TCC) e escreve, a pedido do autor, uma "
    "seção completa, pronta para revisão, em português acadêmico formal (ABNT).\n\n"
    + REGRAS +
    """7. Siga a estrutura do modelo da monografia: use exatamente o título da seção pedida e
   os subtítulos dela que existirem no modelo, na mesma ordem e numeração. Pode criar
   subseções novas só se o modelo não tiver nenhuma e o texto pedir.
8. O conteúdo em <secao_no_modelo> é o que o autor já tem nessa seção: se for rascunho,
   aproveite e melhore as ideias dele (sem perder nada importante); se forem orientações do
   modelo da instituição (ex.: "escreva aqui..."), siga-as e não as copie.
9. Mantenha coerência com <outras_secoes> (tema, problema, objetivos, termos) sem repetir
   o que já foi dito lá.
10. Onde faltar informação que só o autor tem (dados, local, amostra, datas), escreva
   [COMPLETAR: o que falta] em vez de inventar.
11. Formato da saída: markdown simples. Título da seção com "#" (um # por nível, ex.:
   "# 2 FUNDAMENTAÇÃO TEÓRICA", "## 2.1 Conceito de..."), parágrafos separados por linha
   em branco, citação longa com "> ". Comece direto pelo título; não escreva comentários
   antes ou depois do texto da seção.
""")


# ------------------------------------------------------------ fontes / citações
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


def _chave(t: dict) -> tuple:
    return (t["fonte"], t.get("pagina_pdf"), t.get("ordem"))


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


def montar_contextos_autor(ideia: str, fixos: list[dict], recuperados: list[dict],
                           fontes: dict) -> str:
    def ligados(ids):
        return ", ".join(f"{fid} = {abnt.citacao(fontes[fid])}" for fid in ids if fid in fontes)

    partes = []
    if ideia:
        partes.append(f"<ideia_central>\n{ideia}\n</ideia_central>")
    blocos = []
    for c in fixos:
        blocos.append(f'<contexto arquivo="{c["id"]}" artigos="{ligados(c["artigos"])}">\n'
                      f'{c["texto"]}\n</contexto>')
    for ch in recuperados:
        blocos.append(f'<contexto arquivo="{ch["fonte"]}" trecho="{ch["ordem"] + 1}" '
                      f'artigos="{ligados(ch["artigos"])}">\n{ch["texto"]}\n</contexto>')
    if blocos:
        partes.append("<contextos_do_autor>\n" + "\n\n".join(blocos) + "\n</contextos_do_autor>")
    return "\n\n".join(partes)


def _citada(texto: str, f: dict) -> bool:
    aut, ano = abnt.autores_citacao(f), str(f.get("ano"))
    if f"{aut}, {ano}" in texto:
        return True
    primeiro = aut.split(";")[0].replace(" et al.", "").replace(" ...", "").strip()
    # forma narrativa: Silva (2020, p. 3) | Silva e Souza (2020) | Silva et al. (2020)
    return re.search(rf"\b{re.escape(primeiro)}\b[^()]{{0,60}}\({re.escape(ano)}\b", texto) is not None


def fontes_citadas(resposta: str, trechos: list[dict], fontes: dict) -> list[str]:
    usadas = []
    for t in trechos:
        if t["fonte"] not in usadas and _citada(resposta, fontes[t["fonte"]]):
            usadas.append(t["fonte"])
    return usadas


def fontes_citadas_texto(texto: str, fontes: dict) -> list[str]:
    return [fid for fid, f in fontes.items() if _citada(texto, f)]


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


def alertas(resposta: str, trechos: list[dict], fontes: dict) -> str:
    saida = ""
    suspeitas = verificar_citacoes(resposta, trechos, fontes)
    if suspeitas:
        saida += ("\n\n⚠ Citações não conferem com os trechos recuperados (verifique): "
                  + "; ".join(suspeitas))
    nao_rev = [fid for fid in fontes_citadas(resposta, trechos, fontes)
               if not fontes[fid].get("revisado")]
    if nao_rev:
        saida += "\n\n⚠ Metadados ainda não revisados em fontes.json: " + ", ".join(nao_rev)
    return saida


def referencias(resposta: str, trechos: list[dict], fontes: dict) -> str:
    usadas = fontes_citadas(resposta, trechos, fontes)
    return abnt.lista_referencias([fontes[f] for f in usadas]) if usadas else ""


def rodape(resposta: str, trechos: list[dict], fontes: dict) -> str:
    saida = alertas(resposta, trechos, fontes)
    refs = referencias(resposta, trechos, fontes)
    if refs:
        saida += "\n\nREFERÊNCIAS\n\n" + refs
    return saida


def _limitar(texto: str, limite: int, aviso: str = "[... cortado por tamanho ...]") -> str:
    return texto if len(texto) <= limite else texto[:limite] + f"\n{aviso}"


# ------------------------------------------------------------ assistente
class Assistente:
    def __init__(self, buscador):
        self.buscador = buscador
        self.fontes = preparar_fontes(buscador.fontes)
        self.contextos = contextos.carregar(buscador.fontes)
        self.busca_ctx = BuscadorMemoria(contextos.chunks(self.contextos))
        self.ideia = contextos.ideia_central()
        self.historico: list[dict] = []
        self._cliente = None

    @property
    def cliente(self):
        if self._cliente is None:
            import anthropic
            self._cliente = anthropic.Anthropic()  # usa ANTHROPIC_API_KEY
        return self._cliente

    # -------------------------------------------------------- recuperação
    def _contextos(self, consultas: list[str], k: int, titulo_secao: str | None = None):
        fixos = [c for c in self.contextos
                 if c["sempre"] or (titulo_secao and contextos.para_secao(c, titulo_secao))]
        ids = {c["id"] for c in fixos}
        # corta os fixos se passarem do limite
        total, cabem = 0, []
        for c in fixos:
            if total + len(c["texto"]) > config.MAX_CHARS_CONTEXTO_FIXO:
                print(f"  ! README '{c['id']}' não coube inteiro (MAX_CHARS_CONTEXTO_FIXO); "
                      "vai só por busca.")
                ids.discard(c["id"])
                continue
            total += len(c["texto"])
            cabem.append(c)
        recuperados = self.busca_ctx.buscar_multi(consultas, k, filtro=lambda ch: ch["fonte"] not in ids)
        return cabem, recuperados

    def _trechos(self, consultas: list[str], k: int, ligados: list[str],
                 max_por_fonte: int | None = None) -> list[dict]:
        def eh_artigo(c):
            return c.get("tipo", "artigo") == "artigo" and c["fonte"] in self.fontes

        trechos = self.buscador.buscar_multi(consultas, k, filtro=eh_artigo,
                                             max_por_fonte=max_por_fonte)
        vistos = {_chave(t) for t in trechos}
        for fid in ligados:  # artigos citados nos READMEs relevantes
            extra = self.buscador.buscar_multi(
                consultas, config.TRECHOS_POR_ARTIGO_LIGADO,
                filtro=lambda c, fid=fid: eh_artigo(c) and c["fonte"] == fid)
            for t in extra:
                if _chave(t) not in vistos:
                    vistos.add(_chave(t))
                    trechos.append(t)
        return trechos

    def recuperar(self, pergunta: str):
        consulta = pergunta
        if self.historico:  # perguntas de continuação herdam o assunto anterior
            consulta = self.historico[-2]["pergunta"] + " " + pergunta
        fixos, ctx = self._contextos([consulta], config.TOP_K_CONTEXTOS)
        ligados = list(dict.fromkeys(fid for c in fixos + ctx for fid in c["artigos"]))
        trechos = self._trechos([consulta], config.TOP_K, ligados)
        return trechos, fixos, ctx

    # -------------------------------------------------------- chamada ao Claude
    def _chamar(self, sistema: str, mensagens: list[dict], max_tokens: int,
                mostrar: bool = False) -> str:
        params = dict(
            model=config.MODELO_CLAUDE, max_tokens=max_tokens,
            system=[{"type": "text", "text": sistema, "cache_control": {"type": "ephemeral"}}],
            messages=mensagens, output_config={"effort": config.ESFORCO})
        if config.USAR_FALLBACK:
            api = self.cliente.beta.messages
            params.update(betas=["server-side-fallback-2026-07-01"], fallbacks="default")
        else:
            api = self.cliente.messages
        with api.stream(**params) as stream:
            if mostrar:
                for pedaco in stream.text_stream:
                    print(pedaco, end="", flush=True)
                print()
            final = stream.get_final_message()
        if final.stop_reason == "refusal":
            return "⚠ O Claude recusou esta solicitação. Reformule o pedido e tente de novo."
        texto = "".join(b.text for b in final.content if b.type == "text")
        if final.stop_reason == "max_tokens":
            texto += "\n\n⚠ Resposta cortada pelo limite de tokens (aumente MAX_TOKENS em config.py)."
        return texto

    # -------------------------------------------------------- perguntas
    def prompt_para_colar(self, pergunta: str) -> str:
        """Pacote pronto para colar numa conversa do Claude (sem API)."""
        trechos, fixos, ctx = self.recuperar(pergunta)
        refs = abnt.lista_referencias([self.fontes[f] for f in dict.fromkeys(t["fonte"] for t in trechos)])
        return (SISTEMA + "\n" + montar_contextos_autor(self.ideia, fixos, ctx, self.fontes)
                + "\n\n" + montar_contexto(trechos, self.fontes)
                + f"\n\nReferências ABNT das fontes acima (use ao final, só as citadas):\n\n{refs}"
                + f"\n\nPergunta: {pergunta}")

    def perguntar(self, pergunta: str) -> str:
        trechos, fixos, ctx = self.recuperar(pergunta)
        if not trechos:
            return "Não encontrei nada sobre isso nos artigos indexados."
        mensagens = [{"role": h["role"], "content": h["conteudo"]} for h in self.historico]
        mensagens.append({"role": "user", "content":
                          montar_contextos_autor(self.ideia, fixos, ctx, self.fontes)
                          + "\n\n" + montar_contexto(trechos, self.fontes)
                          + f"\n\nPergunta: {pergunta}"})
        texto = self._chamar(SISTEMA, mensagens, config.MAX_TOKENS)

        # histórico guarda só pergunta/resposta (sem trechos) para não estourar contexto
        self.historico += [{"role": "user", "conteudo": pergunta, "pergunta": pergunta},
                           {"role": "assistant", "conteudo": texto}]
        return texto + rodape(texto, trechos, self.fontes)

    # -------------------------------------------------------- seções da monografia
    def _pacote_secao(self, alvo: str, instrucoes: str = "", palavras: int | None = None):
        secoes = monografia.ler_estrutura()
        i = monografia.localizar(secoes, alvo)
        if i is None:
            raise SystemExit(f'Seção "{alvo}" não encontrada. Seções do modelo:\n'
                             + monografia.sumario(secoes)
                             + '\n\nUse o título (ou parte dele), o número ("2.1") ou a posição ("#3").')
        arvore = monografia.subarvore(secoes, i)
        s = secoes[i]
        titulo = monografia.rotulo(s)
        subtitulos = [monografia.rotulo(x) for x in arvore[1:]]
        rascunho = "\n\n".join(p for x in arvore for p in x["paragrafos"])
        # subseção herda o tipo da seção-mãe (ex.: 2.1 dentro de FUNDAMENTAÇÃO TEÓRICA)
        maes = monografia.ancestrais(secoes, i)
        tipo = monografia.tipo_secao(s["titulo"])
        titulo_tipo = s["titulo"]
        for m in reversed(maes):
            if tipo != "padrao":
                break
            tipo, titulo_tipo = monografia.tipo_secao(m["titulo"]), m["titulo"]
        if not palavras:
            palavras = config.PALAVRAS_SECAO.get(tipo, config.PALAVRAS_SECAO["padrao"])
            if maes and tipo == monografia.tipo_secao(titulo_tipo) and titulo_tipo != s["titulo"]:
                # subseção: divide o tamanho do capítulo entre as subseções irmãs
                im = secoes.index(maes[-1])
                irmas = [x for x in monografia.subarvore(secoes, im)[1:] if x["nivel"] == s["nivel"]]
                palavras = max(300, int(round(palavras / max(1, len(irmas)), -2)))

        # consultas para a busca: título + subtítulos + instruções + rascunho + ideia central
        consultas = [s["titulo"] + " " + " ".join(x["titulo"] for x in arvore[1:])]
        consultas += [x["titulo"] for x in arvore[1:]]
        consultas += [instrucoes, rascunho[:1500]]
        if tipo in ("introducao", "resumo", "abstract", "consideracoes", "padrao") or not subtitulos:
            consultas.append(self.ideia[:1500])
        fixos, ctx = self._contextos(consultas, config.TOP_K_CONTEXTOS_SECAO, titulo_secao=s["titulo"])
        consultas += [c["texto"][:1500] for c in fixos]
        ligados = list(dict.fromkeys(fid for c in fixos + ctx for fid in c["artigos"]))
        trechos = self._trechos(consultas, config.TOP_K_SECAO, ligados, config.MAX_POR_FONTE)

        # restante da monografia: seções já geradas + texto do modelo fora desta seção
        meu_arq = monografia.arquivo_secao(i, s)
        geradas = [corpo for arq, corpo in monografia.secoes_geradas() if arq.name != meu_arq.name]
        resto_modelo = monografia.texto_secoes([x for x in secoes if x not in arvore and x["paragrafos"]])
        outras = _limitar("\n\n".join(geradas + ([resto_modelo] if resto_modelo else [])),
                          config.MAX_CHARS_MONOGRAFIA)

        tarefa = [f'Escreva a seção "{titulo}" da monografia (nível de título: {s["nivel"]}).']
        if maes:
            tarefa.append("Ela é subseção de: " + " > ".join(monografia.rotulo(m) for m in maes)
                          + ". Escreva só esta subseção (comece pelo título dela), "
                            "articulada com o capítulo.")
        tarefa.append(f"Orientações para este tipo de seção: {monografia.orientacao(titulo_tipo)}")
        if subtitulos:
            tarefa.append("Subseções do modelo (desenvolva todas, nesta ordem):\n"
                          + "\n".join(f"- {t}" for t in subtitulos))
        tarefa.append(f"Extensão aproximada: {palavras} palavras.")
        if instrucoes:
            tarefa.append(f"Instruções do autor para esta seção: {instrucoes}")

        partes = [montar_contextos_autor(self.ideia, fixos, ctx, self.fontes),
                  f"<estrutura_da_monografia>\n{monografia.sumario(secoes)}\n</estrutura_da_monografia>"]
        if outras:
            partes.append(f"<outras_secoes>\n{outras}\n</outras_secoes>")
        partes.append("<secao_no_modelo>\n" + (rascunho or "(vazia no modelo)") + "\n</secao_no_modelo>")
        partes.append(montar_contexto(trechos, self.fontes))
        partes.append("<tarefa>\n" + "\n\n".join(tarefa) + "\n</tarefa>")
        conteudo = "\n\n".join(p for p in partes if p)

        info = {"indice": i, "secao": s, "titulo": titulo, "arquivo": meu_arq,
                "trechos": trechos, "fixos": fixos, "ctx": ctx, "palavras": palavras}
        return conteudo, info

    def secao_para_colar(self, alvo: str, instrucoes: str = "", palavras: int | None = None):
        conteudo, info = self._pacote_secao(alvo, instrucoes, palavras)
        fontes_ = dict.fromkeys(t["fonte"] for t in info["trechos"])
        refs = abnt.lista_referencias([self.fontes[f] for f in fontes_])
        return (SISTEMA_SECAO + "\n" + conteudo
                + f"\n\nReferências ABNT das fontes acima (só para conferência):\n\n{refs}"), info

    def escrever_secao(self, alvo: str, instrucoes: str = "", palavras: int | None = None):
        conteudo, info = self._pacote_secao(alvo, instrucoes, palavras)
        trechos = info["trechos"]
        if not trechos:
            print("  ! Nenhum trecho de artigo encontrado para esta seção; o texto sairá sem citações.")
        print(f"Escrevendo \"{info['titulo']}\" (~{info['palavras']} palavras) com "
              f"{len(trechos)} trechos de {len({t['fonte'] for t in trechos})} artigos e "
              f"{len(info['fixos']) + len(info['ctx'])} contextos seus...\n")
        texto = self._chamar(SISTEMA_SECAO, [{"role": "user", "content": conteudo}],
                             config.MAX_TOKENS_SECAO, mostrar=True)
        avisos = alertas(texto, trechos, self.fontes)
        refs = referencias(texto, trechos, self.fontes)

        arq = info["arquivo"]
        arq.parent.mkdir(parents=True, exist_ok=True)
        rod = avisos + (f"\n\nREFERÊNCIAS\n\n{refs}" if refs else "")
        arq.write_text(texto.strip() + "\n\n" + monografia.MARCA_RODAPE + rod + "\n", encoding="utf-8")
        docx = monografia.salvar_docx(texto, refs, arq.with_suffix(".docx"))
        return avisos, arq, docx

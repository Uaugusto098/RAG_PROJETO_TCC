"""
RAG do TCC — escreve as seções da monografia e responde perguntas com base nos seus
artigos (PDF), orientado pelos seus READMEs de contexto e pelo modelo da monografia
(Word), com citações e referências ABNT.

Pastas:
  artigos/      PDFs dos artigos científicos (as únicas fontes citadas)
  contextos/    READMEs (.md/.txt/.docx) com a sua ideia sobre os artigos
                + IDEIA_CENTRAL.md (tema, problema, objetivos) — vai em toda chamada
  monografia/   o arquivo Word (.docx) do modelo/rascunho da monografia

Uso:
  python rag.py indexar                   # lê artigos/*.pdf, cria fontes.json e o índice
  python rag.py fontes                    # fontes e se os metadados foram revisados
  python rag.py contextos                 # READMEs carregados e artigos ligados a cada um
  python rag.py estrutura                 # seções encontradas no modelo da monografia

  python rag.py secao "Introdução"        # escreve a seção (API) -> secoes/*.md e *.docx
      [--instrucoes "foque em X"] [--palavras 2000] [--colar]
  python rag.py montar                    # junta as seções geradas em saida/*.docx

  python rag.py perguntar "sua pergunta"  # resposta do Claude via API
  python rag.py chat                      # conversa contínua (salva em respostas.md)
  python rag.py contexto "sua pergunta"   # pacote para colar no chat do Claude (sem API)
  python rag.py referencias               # lista ABNT de todas as fontes
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime

import abnt
import config


def cmd_indexar(_):
    import busca
    import contextos
    import ingestao
    print(f"Lendo PDFs de {config.PASTA_ARTIGOS} ...")
    chunks, fontes = ingestao.ingerir()
    busca.construir(chunks)
    pend = [k for k, f in fontes.items() if not f.get("revisado")]
    print(f"\n{len(fontes)} fontes indexadas.")
    if pend:
        print(f"Revise os metadados em fontes.json e marque \"revisado\": true -> {', '.join(pend)}")
        print("(Não precisa reindexar depois de editar fontes.json.)")
    ctx = contextos.carregar(fontes)
    print(f"{len(ctx)} READMEs de contexto em {config.PASTA_CONTEXTOS.name}/ "
          f"(lidos a cada execução, não precisam de reindexação). "
          f"Ideia central: {'ok' if contextos.ideia_central() else 'não preenchida'}.")


def cmd_fontes(_):
    import ingestao
    for fid, f in ingestao.carregar_fontes().items():
        ok = "✔" if f.get("revisado") else "✗ revisar"
        print(f"[{ok}] {fid:20} {f['arquivo']}")
        print(f"     {abnt.citacao(f)}  ->  {abnt.referencia(f)}\n")


def cmd_contextos(_):
    import contextos
    import ingestao
    ideia = contextos.ideia_central()
    print(f"IDEIA CENTRAL ({config.ARQ_IDEIA_CENTRAL.name}): "
          + (f"{len(ideia.split())} palavras" if ideia else "não preenchida — preencha para melhores resultados"))
    lista = contextos.carregar(ingestao.carregar_fontes())
    if not lista:
        print(f"\nNenhum README em {config.PASTA_CONTEXTOS}/ (aceita .md, .txt, .docx).")
        return
    print()
    for c in lista:
        print(f"• {c['id']}  ({len(c['texto'].split())} palavras)")
        print(f"    artigos ligados: {', '.join(c['artigos']) or '—'}")
        if c["secoes"]:
            print(f"    vai inteiro nas seções: {', '.join(c['secoes'])}")
        if c["sempre"]:
            print("    vai inteiro em todas as chamadas (sempre: sim)")
        if c["faltando"]:
            print(f"    ⚠ não achei no fontes.json: {', '.join(c['faltando'])}")


def cmd_estrutura(_):
    import monografia
    arq = monografia.arquivo_modelo()
    print(f"Modelo: {arq.name if arq else 'nenhum .docx em monografia/ — usando estrutura padrão'}\n")
    secoes = monografia.ler_estrutura(arq)
    for n, s in enumerate(secoes, 1):
        gerada = "✔" if monografia.arquivo_secao(n - 1, s).exists() else " "
        palavras = sum(len(p.split()) for p in s["paragrafos"])
        extra = f"  ({palavras} palavras no modelo)" if palavras else ""
        print(f"[{gerada}] #{n:<3} " + "  " * (s["nivel"] - 1) + monografia.rotulo(s) + extra)
    print('\n✔ = já gerada em secoes/.  Gere com: python rag.py secao "<título, número ou #posição>"')


def cmd_referencias(_):
    import assistente
    import ingestao
    fontes = assistente.preparar_fontes(ingestao.carregar_fontes())
    print("REFERÊNCIAS\n\n" + abnt.lista_referencias(list(fontes.values())))


def _assistente():
    import assistente
    import busca
    return assistente.Assistente(busca.Buscador())


def _salvar(pergunta: str, resposta: str):
    with open(config.BASE / "respostas.md", "a", encoding="utf-8") as f:
        f.write(f"\n\n---\n## {pergunta}\n_{datetime.now():%d/%m/%Y %H:%M}_\n\n{resposta}\n")


def cmd_perguntar(a):
    pergunta = " ".join(a.pergunta)
    resp = _assistente().perguntar(pergunta)
    print(resp)
    _salvar(pergunta, resp)


def cmd_contexto(a):
    texto = _assistente().prompt_para_colar(" ".join(a.pergunta))
    arq = config.BASE / "contexto_para_colar.txt"
    arq.write_text(texto, encoding="utf-8")
    print(texto)
    print(f"\n[salvo em {arq.name} — copie e cole no chat do Claude]")


def cmd_chat(_):
    a = _assistente()
    print("Chat do TCC. Digite sua pergunta (ou 'sair'). Respostas salvas em respostas.md\n")
    while True:
        try:
            p = input("Você: ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if p.lower() in ("sair", "exit", "quit"):
            break
        if p:
            r = a.perguntar(p)
            print(f"\nClaude:\n{r}\n")
            _salvar(p, r)


def cmd_secao(a):
    import monografia
    alvo = " ".join(a.secao)
    assist = _assistente()
    if a.colar:
        texto, info = assist.secao_para_colar(alvo, a.instrucoes, a.palavras)
        arq = config.BASE / f"contexto_secao_{monografia.slug(info['titulo'])}.txt"
        arq.write_text(texto, encoding="utf-8")
        print(f"Pacote da seção \"{info['titulo']}\" salvo em {arq.name} "
              f"({len(info['trechos'])} trechos, {len(texto):,} caracteres).")
        print("Copie o conteúdo e cole numa conversa do Claude.")
        return
    avisos, md, docx = assist.escrever_secao(alvo, a.instrucoes, a.palavras)
    if avisos:
        print(avisos.strip())
    print(f"\nSalvo em: {md.relative_to(config.BASE)}  e  {docx.relative_to(config.BASE)}")


def cmd_montar(_):
    import assistente
    import ingestao
    import monografia
    geradas = monografia.secoes_geradas()
    if not geradas:
        raise SystemExit('Nenhuma seção gerada ainda. Use: python rag.py secao "Introdução"')
    texto = "\n\n".join(corpo for _, corpo in geradas)
    fontes = assistente.preparar_fontes(ingestao.carregar_fontes())
    usadas = assistente.fontes_citadas_texto(texto, fontes)
    refs = abnt.lista_referencias([fontes[f] for f in usadas])
    destino = config.PASTA_SAIDA / "monografia_rascunho.docx"
    monografia.salvar_docx(texto, refs, destino)
    print(f"{len(geradas)} seções + {len(usadas)} referências -> {destino.relative_to(config.BASE)}")
    for arq, _ in geradas:
        print(f"  • {arq.name}")


def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help", "ajuda"):
        print(__doc__)
        return
    p = argparse.ArgumentParser(prog="rag.py", description="RAG do TCC")
    sub = p.add_subparsers(dest="cmd", required=True)
    for nome, fn in [("indexar", cmd_indexar), ("fontes", cmd_fontes), ("contextos", cmd_contextos),
                     ("estrutura", cmd_estrutura), ("referencias", cmd_referencias),
                     ("chat", cmd_chat), ("montar", cmd_montar)]:
        sub.add_parser(nome).set_defaults(fn=fn)
    for nome, fn in [("perguntar", cmd_perguntar), ("contexto", cmd_contexto)]:
        sp = sub.add_parser(nome)
        sp.add_argument("pergunta", nargs="+")
        sp.set_defaults(fn=fn)
    sp = sub.add_parser("secao", help="escreve uma seção da monografia")
    sp.add_argument("secao", nargs="+", help='título, número ("2.1") ou posição ("#3")')
    sp.add_argument("--instrucoes", "-i", default="", help="orientações extras para esta seção")
    sp.add_argument("--palavras", "-p", type=int, default=None, help="tamanho aproximado")
    sp.add_argument("--colar", action="store_true", help="só gera o pacote para colar no chat (sem API)")
    sp.set_defaults(fn=cmd_secao)

    a = p.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()

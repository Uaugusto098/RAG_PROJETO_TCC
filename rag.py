"""
RAG do TCC — respostas com base nos seus artigos, com citações e referências ABNT.

Uso:
  python rag.py indexar                 # lê artigos/*.pdf, cria fontes.json e o índice
  python rag.py fontes                  # mostra as fontes e se os metadados foram revisados
  python rag.py perguntar "sua pergunta"  # resposta do Claude via API
  python rag.py chat                    # conversa contínua (salva em respostas.md)
  python rag.py contexto "sua pergunta"   # gera o pacote para colar no chat do Claude (sem API)
  python rag.py referencias             # lista ABNT de todas as fontes
"""
from __future__ import annotations

import sys
from datetime import datetime

import abnt
import config


def cmd_indexar():
    import busca
    import ingestao
    print(f"Lendo PDFs de {config.PASTA_ARTIGOS} ...")
    chunks, fontes = ingestao.ingerir()
    busca.construir(chunks)
    pend = [k for k, f in fontes.items() if not f.get("revisado")]
    print(f"\n{len(fontes)} fontes indexadas.")
    if pend:
        print(f"Revise os metadados em fontes.json e marque \"revisado\": true -> {', '.join(pend)}")
        print("(Não precisa reindexar depois de editar fontes.json.)")


def cmd_fontes():
    import ingestao
    for fid, f in ingestao.carregar_fontes().items():
        ok = "✔" if f.get("revisado") else "✗ revisar"
        print(f"[{ok}] {fid:20} {f['arquivo']}")
        print(f"     {abnt.citacao(f)}  ->  {abnt.referencia(f)}\n")


def cmd_referencias():
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


def cmd_perguntar(pergunta: str):
    resp = _assistente().perguntar(pergunta)
    print(resp)
    _salvar(pergunta, resp)


def cmd_contexto(pergunta: str):
    texto = _assistente().prompt_para_colar(pergunta)
    arq = config.BASE / "contexto_para_colar.txt"
    arq.write_text(texto, encoding="utf-8")
    print(texto)
    print(f"\n[salvo em {arq.name} — copie e cole no chat do Claude]")


def cmd_chat():
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


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return
    cmd, args = sys.argv[1], " ".join(sys.argv[2:])
    comandos = {"indexar": cmd_indexar, "fontes": cmd_fontes, "referencias": cmd_referencias,
                "chat": cmd_chat}
    if cmd in comandos:
        comandos[cmd]()
    elif cmd in ("perguntar", "contexto"):
        if not args:
            sys.exit(f'Uso: python rag.py {cmd} "sua pergunta"')
        (cmd_perguntar if cmd == "perguntar" else cmd_contexto)(args)
    else:
        print(__doc__)


if __name__ == "__main__":
    main()

# RAG do TCC (Python + Claude) com citações ABNT

Responde perguntas **somente com base nos seus PDFs**, com citação no texto
(NBR 10520:2023) com **página exata** e lista de **referências** (NBR 6023:2018).

## Como funciona

1. `indexar` lê cada PDF **página por página** e corta em trechos que nunca
   atravessam páginas — por isso a página citada é exata.
2. A busca (BM25 + semântica opcional) acha os trechos mais relevantes à pergunta.
3. O Claude recebe os trechos, cada um já com sua citação pronta, ex. `(Silva, 2020, p. 47)`,
   e é obrigado a usar só elas.
4. O código confere as citações da resposta contra os trechos (avisa se aparecer
   alguma inventada) e anexa as **REFERÊNCIAS geradas pelo código** a partir de
   `fontes.json` — a referência não depende da LLM, então sai sempre igual e correta.

## Instalação

```bash
pip install -r requirements.txt
pip install sentence-transformers      # opcional, recomendado
```

## Uso

```bash
# 1. coloque os PDFs em artigos/
python rag.py indexar

# 2. abra fontes.json e revise cada fonte (veja abaixo), marque "revisado": true
python rag.py fontes          # confere como ficaram citação e referência

# 3a. com chave da API do Claude
export ANTHROPIC_API_KEY="sk-ant-..."     # Windows: set ANTHROPIC_API_KEY=...
python rag.py perguntar "Quais os efeitos da sala de aula invertida?"
python rag.py chat                         # conversa; tudo salvo em respostas.md

# 3b. sem API: gera o pacote (regras + trechos + referências) para colar no chat do Claude
python rag.py contexto "Quais os efeitos da sala de aula invertida?"

python rag.py referencias      # lista ABNT de todas as fontes
```

## fontes.json — o que revisar (importante)

PDFs raramente trazem metadados confiáveis; o `indexar` cria só um rascunho.

```json
"oliveira2021": {
  "arquivo": "oliveira2021.pdf",
  "revisado": true,
  "tipo": "artigo",
  "autores": [{"sobrenome": "Oliveira", "nome": "Maria Clara"}],
  "titulo": "Aprendizagem ativa no ensino superior",
  "subtitulo": "",
  "periodico": "Revista Brasileira de Educação",
  "local": "Rio de Janeiro",
  "volume": "26", "numero": "3", "paginas": "45-60",
  "mes": "7", "ano": "2021",
  "doi": "10.1590/abc.2021.123",
  "url": "", "acesso": "",
  "primeira_pagina": 45
}
```

- **`primeira_pagina`**: número impresso da 1ª página do PDF. Se o artigo ocupa as
  p. 45–60 da revista, ponha 45; a página 3 do arquivo vira `p. 47` na citação.
- **`tipo`**: `artigo`, `livro`, `capitulo`, `tese`, `dissertacao`, `tcc`, `evento`, `web`.
  - livro: `editora`, `edicao`, `local`
  - capitulo: `organizadores` (ex. "SILVA, João (org.)"), `livro`, `editora`, `paginas`
  - tese/dissertacao/tcc: `instituicao`, `local`, `grau` (opcional)
  - evento: `evento`, `edicao_evento`, `local_evento`, `anais`, `editora`, `paginas`
  - web/online: `url`, `acesso` (ex. "30 out. 2026")
- Editou o `fontes.json`? Não precisa reindexar. Adicionou PDF novo? Rode `indexar`.

## Ajustes (config.py)

- `CITACAO_MAIUSCULA = True` → formato antigo `(SILVA, 2020, p. 5)`, se sua
  instituição ainda exigir.
- `TOP_K` → quantos trechos vão para o Claude por pergunta.
- `MODELO_CLAUDE` → modelo usado na API.

## Limitações

- PDF escaneado (imagem) não tem texto: rode OCR antes (ex. `ocrmypdf entrada.pdf saida.pdf`).
- Confira sempre as citações diretas no PDF antes de entregar o TCC.

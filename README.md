# RAG do TCC (Python + Claude): escreve a monografia com citações ABNT

Escreve as **seções da monografia** (introdução, fundamentação teórica, metodologia...)
e responde perguntas **com base nos seus PDFs**, guiado pela **sua ideia** (READMEs de
contexto) e pelo **modelo da monografia em Word**. As citações seguem a NBR 10520:2023,
com **página exata**, e a lista de **referências** segue a NBR 6023:2018.

## As 3 entradas

| Pasta | O que colocar | Para que serve |
|---|---|---|
| `artigos/` | PDFs dos artigos científicos | São as **únicas fontes citadas** no texto |
| `contextos/` | READMEs `.md`, `.txt` ou `.docx` com seus resumos e sua ideia sobre os artigos, mais o `IDEIA_CENTRAL.md` | Dizem ao Claude **como você quer usar cada artigo** e que argumento construir. Não são citados |
| `monografia/` | O arquivo Word (`.docx`) da monografia: modelo da instituição ou seu rascunho | Define **as seções e subseções**. O texto já escrito em cada uma é usado como rascunho ou orientação |

## Como funciona

1. `indexar` lê cada PDF **página por página** e corta em trechos que nunca
   atravessam páginas. Por isso a página citada é exata.
2. Ao escrever uma seção, o programa:
   - lê o `.docx` e acha a seção pedida, as subseções dela e o que já está escrito ali;
   - inclui a **ideia central** completa e os **READMEs** relevantes (os marcados para essa
     seção vão inteiros, os outros entram por busca);
   - busca os trechos de artigos mais relevantes (busca híbrida BM25 + semântica opcional,
     com várias consultas e no máximo N trechos por artigo, para variar os autores), e
     **puxa também trechos dos artigos citados nos seus READMEs**;
   - inclui as outras seções (do modelo e as já geradas), para o texto ficar coerente.
3. O Claude escreve a seção usando só as citações prontas dos trechos, ex. `(Silva, 2020, p. 47)`.
4. O código confere as citações (avisa se aparecer alguma inventada) e gera as
   **REFERÊNCIAS** a partir de `fontes.json`. A referência não depende da LLM.
5. Cada seção é salva em `secoes/` como `.md` e `.docx` (formatação ABNT). `montar`
   junta tudo num só `.docx`.

## Instalação

```bash
pip install -r requirements.txt
pip install sentence-transformers      # opcional, recomendado
export ANTHROPIC_API_KEY="sk-ant-..."     # Windows: set ANTHROPIC_API_KEY=...
```

## Passo a passo

```bash
# 1. Artigos: coloque os PDFs em artigos/ e indexe
python rag.py indexar
#    abra fontes.json, revise cada fonte e marque "revisado": true (veja abaixo)
python rag.py fontes

# 2. Sua ideia: preencha contextos/IDEIA_CENTRAL.md e crie um README por artigo
#    (copie contextos/_MODELO_resumo_artigo.md)
python rag.py contextos        # mostra os READMEs e a que artigos cada um está ligado

# 3. Modelo: coloque o .docx da monografia em monografia/
python rag.py estrutura        # lista as seções encontradas (#1, #2, ...)

# 4. Escreva as seções
python rag.py secao "Introdução"
python rag.py secao "Fundamentação teórica" --palavras 5000
python rag.py secao 2.1 --instrucoes "compare Almeida e Komagata sobre propósito"
python rag.py secao "#6"                     # pela posição mostrada em `estrutura`

# 5. Junte tudo
python rag.py montar           # -> saida/monografia_rascunho.docx
```

Sem API? `python rag.py secao "Introdução" --colar` gera um arquivo
`contexto_secao_*.txt` com tudo (regras, ideia, READMEs, modelo, trechos) para colar
numa conversa do Claude.

Outros comandos:

```bash
python rag.py perguntar "Quais os efeitos da sala de aula invertida?"
python rag.py chat                         # conversa; tudo salvo em respostas.md
python rag.py contexto "sua pergunta"      # pacote para colar no chat (sem API)
python rag.py referencias                  # lista ABNT de todas as fontes
```

## READMEs de contexto (`contextos/`)

São os seus resumos dos artigos, escritos **com a sua ideia**: o que o artigo diz, o
que interessa a você, como isso se liga ao seu tema, com que outro autor ele conversa.
O Claude usa esses textos para decidir **o que** escrever e **quais trechos** usar, mas
sempre cita os PDFs. Se a sua ideia não estiver nos artigos, ele escreve como argumento
do próprio trabalho ou marca `[PRECISA DE FONTE]`.

- **`IDEIA_CENTRAL.md`**: tema, problema, objetivos, justificativa, hipótese,
  metodologia, como usar os artigos e preferências de escrita. Vai inteiro em **toda** chamada.
- **Um README por artigo** (ou por tema). Cabeçalho opcional:

```markdown
---
artigos: almeida2021, komagata2019      # ids do fontes.json ou nomes dos PDFs
secoes: Fundamentação teórica           # nessas seções o README vai inteiro
sempre: nao                             # sim = vai inteiro em toda chamada
---
# Minha leitura de Almeida (2021)
O artigo mostra X, o que reforça meu argumento de que Y...
```

- Ligação automática com o artigo: se o README tiver **o mesmo nome do PDF ou do id**
  (`almeida2021.md`) ou se o **id aparecer no texto**, os trechos daquele artigo são
  puxados junto quando o README for relevante.
- Arquivos que começam com `_` são ignorados (modelos). Comentários `<!-- -->` também.
- Editou um README? **Não precisa reindexar**: eles são lidos a cada execução.

## Modelo da monografia (`monografia/`)

- Use os estilos de título do Word (**Título 1, Título 2...**). Sem estilos, o programa
  reconhece títulos numerados em MAIÚSCULAS ou negrito (`2 FUNDAMENTAÇÃO TEÓRICA`,
  `2.1 Conceito de...`) e RESUMO, ABSTRACT, CONCLUSÃO etc.
- Sumário, listas e referências do modelo são ignorados.
- Texto embaixo de um título vai para o Claude ao escrever aquela seção. Se for um
  rascunho seu, ele aproveita e melhora. Se for uma orientação ("escreva aqui..."), ele segue.
- Ao gerar uma subseção (ex. `2.1`), ela recebe as orientações do capítulo-mãe e uma
  parte proporcional do tamanho dele.
- Com mais de um `.docx`, o mais recente é usado (ou defina `ARQUIVO_MONOGRAFIA` no `config.py`).
- Sem `.docx`, a estrutura padrão é usada: Resumo, Introdução, Fundamentação teórica,
  Metodologia, Resultados e discussão, Considerações finais.
- Os `.docx` gerados reutilizam os estilos, as margens e o cabeçalho/rodapé do seu modelo
  (só o conteúdo é trocado). Sem modelo, saem em Times 12, espaço 1,5, margens 3/2 cm,
  recuo de 1,25 cm e citação longa com recuo de 4 cm em fonte 10. Se os seus títulos têm
  numeração automática no Word, apague o número duplicado.

## fontes.json: o que revisar (importante)

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

- `PALAVRAS_SECAO`: tamanho-alvo por tipo de seção (ou `--palavras` na hora).
- `TOP_K_SECAO`, `MAX_POR_FONTE`, `TOP_K_CONTEXTOS_SECAO`: quantos trechos de artigos
  e de READMEs entram ao escrever uma seção.
- `TOP_K`, `TOP_K_CONTEXTOS`: o mesmo para `perguntar`/`chat`.
- `MAX_CHARS_CONTEXTO_FIXO`, `MAX_CHARS_MONOGRAFIA`: limites do que vai inteiro.
- `MODELO_CLAUDE`, `ESFORCO`: modelo e nível de esforço (`low` ... `max`).
- `USAR_FALLBACK = True`: se o Claude recusar por engano, o servidor tenta de novo em
  outro modelo automaticamente.
- `CITACAO_MAIUSCULA = True`: formato antigo `(SILVA, 2020, p. 5)`, se sua
  instituição ainda exigir.

## Limitações

- PDF escaneado (imagem) não tem texto: rode OCR antes (ex. `ocrmypdf entrada.pdf saida.pdf`).
- O texto gerado é um **rascunho de qualidade**, não a versão final. Revise o argumento,
  preencha os `[COMPLETAR: ...]` e `[PRECISA DE FONTE]` e confira no PDF as citações
  diretas e as que o programa marcar com ⚠.

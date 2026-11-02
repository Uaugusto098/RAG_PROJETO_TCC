"""Configurações do RAG do TCC. Ajuste aqui."""
from pathlib import Path

BASE = Path(__file__).parent
PASTA_ARTIGOS = BASE / "artigos"          # PDFs dos artigos científicos (fontes citáveis)
PASTA_CONTEXTOS = BASE / "contextos"      # READMEs (.md/.txt/.docx) com SUA ideia sobre os artigos
PASTA_MONOGRAFIA = BASE / "monografia"    # arquivo Word (.docx) do modelo/rascunho da monografia
PASTA_SECOES = BASE / "secoes"            # seções geradas (.md e .docx)
PASTA_SAIDA = BASE / "saida"              # monografia montada (python rag.py montar)
ARQ_FONTES = BASE / "fontes.json"         # metadados ABNT de cada PDF (revise!)
PASTA_INDICE = BASE / ".indice"

# Contexto principal: tema, problema, objetivos, hipótese... Vai inteiro em TODA chamada.
ARQ_IDEIA_CENTRAL = PASTA_CONTEXTOS / "IDEIA_CENTRAL.md"
# Se houver mais de um .docx em monografia/, qual usar (nome do arquivo). None = o mais recente.
ARQUIVO_MONOGRAFIA = None

# --- Fragmentação (chunks nunca atravessam páginas -> página exata) ---
TAM_CHUNK = 1200        # caracteres
SOBREPOSICAO = 200

# --- Busca ---
TOP_K = 8               # trechos de artigos por pergunta (perguntar/chat)
TOP_K_CONTEXTOS = 4     # trechos dos seus READMEs por pergunta
TOP_K_SECAO = 24        # trechos de artigos ao escrever uma seção da monografia
TOP_K_CONTEXTOS_SECAO = 10
MAX_POR_FONTE = 6       # no máx. N trechos do mesmo artigo por seção (diversidade de autores)
TRECHOS_POR_ARTIGO_LIGADO = 3  # trechos extras de cada artigo citado num README relevante
USAR_EMBEDDINGS = True  # usa busca semântica se sentence-transformers estiver instalado
MODELO_EMBEDDINGS = "intfloat/multilingual-e5-small"

# --- Limites de contexto enviado ao Claude (caracteres) ---
MAX_CHARS_CONTEXTO_FIXO = 30000   # READMEs marcados para a seção (secoes:) ou "sempre: sim"
MAX_CHARS_MONOGRAFIA = 40000      # texto do restante da monografia + seções já geradas

# --- LLM (Claude) ---
MODELO_CLAUDE = "claude-opus-5-5"
MAX_TOKENS = 16000          # perguntar/chat
MAX_TOKENS_SECAO = 64000    # geração de seção (resposta transmitida em streaming)
ESFORCO = "high"            # low | medium | high | xhigh | max
# Se o Claude recusar a resposta por engano (classificador de segurança), o servidor
# tenta de novo automaticamente em outro modelo. False desliga.
USAR_FALLBACK = True

# Tamanho-alvo (palavras) por tipo de seção; mude com --palavras na linha de comando.
PALAVRAS_SECAO = {
    "resumo": 300,
    "abstract": 300,
    "introducao": 1500,
    "fundamentacao": 4000,
    "metodologia": 1500,
    "resultados": 3000,
    "consideracoes": 1000,
    "padrao": 1500,
}

# --- ABNT ---
# NBR 10520:2023 -> (Silva, 2020, p. 5). True -> formato antigo (SILVA, 2020, p. 5)
CITACAO_MAIUSCULA = False
# NBR 6023:2018 -> com 4+ autores, usar "et al." na referência (False lista todos)
REFERENCIA_ET_AL = True

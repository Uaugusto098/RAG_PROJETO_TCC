"""Configurações do RAG do TCC. Ajuste aqui."""
from pathlib import Path

BASE = Path(__file__).parent
PASTA_ARTIGOS = BASE / "artigos"          # coloque seus PDFs aqui
ARQ_FONTES = BASE / "fontes.json"         # metadados ABNT de cada PDF (revise!)
PASTA_INDICE = BASE / ".indice"

# --- Fragmentação (chunks nunca atravessam páginas -> página exata) ---
TAM_CHUNK = 1200        # caracteres
SOBREPOSICAO = 200

# --- Busca ---
TOP_K = 8               # trechos enviados ao Claude por pergunta
USAR_EMBEDDINGS = True  # usa busca semântica se sentence-transformers estiver instalado
MODELO_EMBEDDINGS = "intfloat/multilingual-e5-small"

# --- LLM (Claude) ---
MODELO_CLAUDE = "claude-opus-5-5"
MAX_TOKENS = 4000

# --- ABNT ---
# NBR 10520:2023 -> (Silva, 2020, p. 5). True -> formato antigo (SILVA, 2020, p. 5)
CITACAO_MAIUSCULA = False
# NBR 6023:2018 -> com 4+ autores, usar "et al." na referência (False lista todos)
REFERENCIA_ET_AL = True

FROM python:3.10-slim

# ── System deps ──
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# ── Python deps (cache layer) ──
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# ── App code ──
COPY . .

# ── HuggingFace Spaces: port 7860 ──
ENV PORT=7860
EXPOSE 7860

# ── Pre-download models at build time (faster startup) ──
RUN python -c "\
from sentence_transformers import SentenceTransformer, CrossEncoder; \
SentenceTransformer('BAAI/bge-m3'); \
CrossEncoder('BAAI/bge-reranker-v2-m3'); \
print('Models cached OK')" || echo "Model pre-download skipped"

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "7860", "--workers", "1"]

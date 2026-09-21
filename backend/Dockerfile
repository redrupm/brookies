# Build context is the repo root (brookies/), since requirements.txt lives
# there and this Dockerfile needs both it and backend/. Build with:
#   docker build -f backend/Dockerfile -t brookies-backend .
FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HF_HOME=/opt/hf-cache \
    PORT=8000

WORKDIR /app

COPY requirements.txt .
# The CPU-only torch build pinned in requirements.txt isn't on the default
# PyPI index for every version, so point pip at PyTorch's CPU wheel index too.
RUN pip install --no-cache-dir --extra-index-url https://download.pytorch.org/whl/cpu -r requirements.txt \
    && pip install --no-cache-dir gunicorn

COPY backend/ backend/

# Bake the FinBERT weights into the image at build time. Without this, every
# cold start (the app scales to zero when idle to stay cheap) would have to
# re-download ~440MB from Hugging Face Hub before it could serve a request.
RUN python -c "from transformers import AutoModel, AutoTokenizer; AutoTokenizer.from_pretrained('ProsusAI/finbert'); AutoModel.from_pretrained('ProsusAI/finbert')"

WORKDIR /app/backend
EXPOSE 8000

# Single worker: the FinBERT + trend models are loaded into memory once per
# worker process, and this app is sized for low personal traffic, not
# concurrent request volume. Bump --threads if requests start queueing.
CMD ["gunicorn", "-w", "1", "--threads", "4", "-b", "0.0.0.0:8000", "--timeout", "120", "app:app"]

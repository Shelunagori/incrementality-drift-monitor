# Backend image for Railway. Build context is the REPO ROOT (the agent reads docs/METHODOLOGY.md):
#   docker build -f backend/Dockerfile -t idm-backend .
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH=/opt/venv/bin:$PATH

RUN pip install --no-cache-dir "uv>=0.12,<0.13"

WORKDIR /app/backend
COPY backend/pyproject.toml backend/uv.lock backend/.python-version ./
RUN uv sync --frozen --no-dev --no-install-project

COPY backend/ ./
COPY docs/ /app/docs/
# Synthetic CSVs baked into the image so the first start only has to load them.
RUN python -m scripts.generate_data && chmod +x start.sh

EXPOSE 8000
CMD ["./start.sh"]

# Cognifold service image — FastAPI app served by uvicorn.
# Built and smoke-tested in CI (.github/workflows/ci.yml docker-build job)
# and used for GCP Cloud Run deployment.
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8000

WORKDIR /app

# Install the package first using only the build inputs so the dependency
# layer is cached across source-only changes.
COPY pyproject.toml README.md ./
COPY src/ ./src/

RUN pip install ".[service,agent,search]"

EXPOSE 8000

# wsgi:app is the module-level ASGI app (create_app from env settings).
CMD ["sh", "-c", "uvicorn cognifold.service.wsgi:app --host 0.0.0.0 --port ${PORT:-8000}"]

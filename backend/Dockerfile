ARG PYTHON_IMAGE=python:3.12-slim
FROM ${PYTHON_IMAGE} AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1 \
    OMP_THREAD_LIMIT=1
RUN apt-get update && apt-get install -y --no-install-recommends \
        tesseract-ocr tesseract-ocr-kaz tesseract-ocr-rus tesseract-ocr-eng \
        libzbar0 libmagic1 libglib2.0-0 fonts-dejavu-core curl \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

FROM base AS test
COPY requirements-dev.txt .
RUN pip install -r requirements-dev.txt
COPY . .
CMD ["pytest", "-q"]

FROM base AS runtime
RUN groupadd -r planit && useradd -r -g planit -d /app planit
COPY --chown=planit:planit . .
RUN chmod +x docker/entrypoint.sh && mkdir -p /data/storage && chown -R planit:planit /data
USER planit
ENV STORAGE_LOCAL_PATH=/data/storage
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=180s --retries=3 CMD curl -fsS http://localhost:8000/api/health || exit 1
ENTRYPOINT ["docker/entrypoint.sh"]
CMD ["api"]

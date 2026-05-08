FROM python:3.12-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
    libgomp1 \
    tini \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --upgrade pip \
    && pip install -r requirements.txt

COPY app ./app
COPY start.sh ./start.sh
COPY .env.example ./.env.example
COPY README.md ./README.md
COPY CONTRIBUTING.md ./CONTRIBUTING.md

RUN useradd --create-home --uid 1000 --shell /bin/bash appuser \
    && chown -R appuser:appuser /app \
    && chmod +x /app/start.sh

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import json, urllib.request; response = urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=5); payload = json.load(response); raise SystemExit(0 if response.status == 200 and payload.get('data', {}).get('status') == 'ok' else 1)"

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["bash", "/app/start.sh"]
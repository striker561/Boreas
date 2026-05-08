FROM python:3.12-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    OMP_NUM_THREADS=2 \
    OMP_WAIT_POLICY=PASSIVE \
    MALLOC_ARENA_MAX=2 \
    U2NET_HOME=/home/appuser/.u2net

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
    && mkdir -p /home/appuser/.u2net \
    && chown -R appuser:appuser /app \
    && chown -R appuser:appuser /home/appuser/.u2net \
    && chmod +x /app/start.sh

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=90s --retries=3 \
    CMD python -c "import os, sys, urllib.request; response = urllib.request.urlopen(f\"http://127.0.0.1:{os.environ.get('PORT', '8000')}/\", timeout=5); sys.exit(0 if response.status == 200 else 1)"

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["bash", "/app/start.sh"]
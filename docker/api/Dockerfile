###############################################################################
# Stage 1 — install dependencies
###############################################################################
FROM python:3.11-slim AS builder

WORKDIR /build
COPY pyproject.toml .
COPY src/ ./src/

RUN pip install --no-cache-dir --no-compile ".[otel]" \
    && SITE=/usr/local/lib/python3.11/site-packages \
    && find $SITE -type d \( -name "__pycache__" -o -name "tests" -o -name "test" -o -name "testing" \) -exec rm -rf {} + 2>/dev/null; \
    find $SITE -type f \( -name "*.pyc" -o -name "*.pyo" \) -delete 2>/dev/null; \
    find $SITE -type f -name "*.so" -exec strip --strip-unneeded {} + 2>/dev/null; \
    rm -rf $SITE/pip $SITE/setuptools $SITE/wheel $SITE/pkg_resources 2>/dev/null; \
    true

###############################################################################
# Stage 2 — minimal runtime
###############################################################################
FROM python:3.11-slim AS runtime

RUN groupadd -r appuser && useradd -r -g appuser -s /sbin/nologin appuser \
    && mkdir -p /tmp/ai-platform-uploads && chown appuser:appuser /tmp/ai-platform-uploads \
    && mkdir -p /home/appuser/.cache && chown -R appuser:appuser /home/appuser

WORKDIR /app

COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin/uvicorn /usr/local/bin/uvicorn
COPY src/ ./src/

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HOME=/home/appuser \
    FASTEMBED_CACHE_PATH=/tmp/fastembed-cache

EXPOSE 8000

USER appuser

CMD ["uvicorn", "src.ai_platform.main:app", "--host", "0.0.0.0", "--port", "8000"]

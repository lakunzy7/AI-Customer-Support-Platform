###############################################################################
# Stage 1 — install dependencies
###############################################################################
FROM python:3.11-slim AS builder

WORKDIR /build
COPY pyproject.toml .
COPY src/ ./src/
RUN pip install --no-cache-dir .

###############################################################################
# Stage 2 — runtime
###############################################################################
FROM python:3.11-slim AS runtime

RUN groupadd -r appuser && useradd -r -g appuser -s /sbin/nologin appuser

WORKDIR /app

COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin/uvicorn /usr/local/bin/uvicorn
COPY src/ ./src/

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

EXPOSE 8000

USER appuser

CMD ["uvicorn", "src.ai_platform.main:app", "--host", "0.0.0.0", "--port", "8000"]

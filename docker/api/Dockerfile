###############################################################################
# Stage 1 — build dependencies
###############################################################################
FROM python:3.11-slim AS builder

WORKDIR /build
COPY pyproject.toml .
RUN pip install --no-cache-dir build \
    && pip wheel --no-cache-dir --wheel-dir /wheels -e .

###############################################################################
# Stage 2 — runtime
###############################################################################
FROM python:3.11-slim AS runtime

RUN groupadd -r appuser && useradd -r -g appuser -s /sbin/nologin appuser

WORKDIR /app

COPY --from=builder /wheels /wheels
RUN pip install --no-cache-dir /wheels/*.whl && rm -rf /wheels

COPY src/ ./src/

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

EXPOSE 8000

USER appuser

CMD ["uvicorn", "src.ai_platform.main:app", "--host", "0.0.0.0", "--port", "8000"]

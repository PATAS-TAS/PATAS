# PATAS Production Dockerfile
# Multi-stage build for optimized production image

# =============================================================================
# Stage 1: Build stage
# =============================================================================
FROM python:3.14-slim as builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install poetry
RUN pip install --no-cache-dir poetry==1.7.1

# Copy dependency files
COPY pyproject.toml poetry.lock* ./

# Export requirements (without dev dependencies)
RUN poetry export -f requirements.txt --without-hashes --without dev > requirements.txt

# Install dependencies to a virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app/ ./app/
COPY integration/ ./integration/
COPY scripts/ ./scripts/

# Install the application
RUN pip install --no-cache-dir -e .

# =============================================================================
# Stage 2: Production runtime
# =============================================================================
FROM python:3.14-slim as production

# Security: Run as non-root user
RUN groupadd --gid 1000 patas && \
    useradd --uid 1000 --gid patas --shell /bin/bash --create-home patas

WORKDIR /app

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy application code
COPY --from=builder /app/app ./app
COPY --from=builder /app/integration ./integration
COPY --from=builder /app/scripts ./scripts
COPY --from=builder /app/pyproject.toml ./

# Create data and logs directories with proper permissions
RUN mkdir -p /app/data /app/logs && \
    chown -R patas:patas /app

# Switch to non-root user
USER patas

# Environment variables for production
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    ENVIRONMENT=production \
    API_HOST=0.0.0.0 \
    API_PORT=8000 \
    LOG_LEVEL=INFO \
    PRIVACY_MODE=STRICT

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/healthz || exit 1

# Proper signal handling with exec
ENTRYPOINT ["python", "-m", "uvicorn"]
CMD ["app.api.run:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]

# =============================================================================
# Stage 3: Development runtime (optional, for local testing)
# =============================================================================
FROM production as development

USER root

# Install development dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy poetry files and install dev dependencies
COPY --from=builder /app/pyproject.toml /app/poetry.lock* ./
RUN pip install --no-cache-dir poetry==1.7.1 && \
    poetry config virtualenvs.create false && \
    poetry install --only dev

USER patas

# Development overrides
ENV ENVIRONMENT=development \
    API_RELOAD=true \
    LOG_LEVEL=DEBUG

CMD ["app.api.run:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]


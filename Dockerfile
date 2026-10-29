# Multi-stage Docker build for Cryptobot
FROM python:3.11-slim as builder

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libpq-dev \
    libssl-dev \
    libffi-dev \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
WORKDIR /app
COPY requirements.txt pyproject.toml ./
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r requirements.txt

# =============================================================================
# Runtime stage
# =============================================================================
FROM python:3.11-slim as runtime

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    libssl3 \
    libffi8 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd -m -u 1000 -s /bin/bash cryptobot

WORKDIR /app

# Copy Python packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code
COPY --chown=cryptobot:cryptobot cryptobot/ ./cryptobot/
COPY --chown=cryptobot:cryptobot config/ ./config/
COPY --chown=cryptobot:cryptobot main.py ./
COPY --chown=cryptobot:cryptobot pyproject.toml ./

# Create data directories
RUN mkdir -p /app/data/logs /app/data/checkpoints /app/data/models /app/data/memory && \
    chown -R cryptobot:cryptobot /app/data

USER cryptobot

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

EXPOSE 8000 8080 8081

CMD ["python", "-m", "cryptobot"]
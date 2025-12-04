# Pi-hole Wizard Web - Docker Image
# Multi-arch build for AMD64 and ARM (Raspberry Pi)

FROM python:3.11-slim

# Install system dependencies (including Docker CLI for Pi-hole installation)
RUN apt-get update && apt-get install -y \
    curl \
    iproute2 \
    net-tools \
    lsof \
    gcc \
    python3-dev \
    docker.io \
    docker-compose \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Install Python dependencies
COPY pyproject.toml ./
RUN pip install --no-cache-dir \
    fastapi>=0.109.0 \
    uvicorn[standard]>=0.27.0 \
    python-multipart>=0.0.6 \
    anthropic>=0.18.0 \
    netifaces>=0.11.0 \
    pydantic>=2.0.0

# Copy application code
COPY backend/ ./backend/
COPY frontend/ ./frontend/

# Create output directory
RUN mkdir -p /app/output

# Expose port
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=3s \
    CMD curl -f http://localhost:8080/health || exit 1

# Run the application
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8080"]

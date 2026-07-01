# Yandex Search API MCP Server Dockerfile
# Base image with Python 3.10
FROM python:3.10-slim as builder

# Image metadata
LABEL org.opencontainers.image.title="Yandex Search API MCP Server (Async Mode)"
LABEL org.opencontainers.image.description="MCP server for Yandex Search API v2 with async mode and SQLite storage"
LABEL org.opencontainers.image.vendor="Yandex LLC"
LABEL org.opencontainers.image.version="1.0.0"
LABEL org.opencontainers.image.licenses="Apache-2.0"

# Install dependencies
RUN pip install requests mcp[cli]

# Final image
WORKDIR /app
ENV PATH=/root/.local/bin:$PATH

# Copy application files
COPY --chown=1000:1000 server.py detail.py storage.py ./

# Create data directory for SQLite
RUN mkdir -p /app/data && chown 1000:1000 /app/data

# Environment setup
ENV PATH=/root/.local/bin:$PATH
ENV PYTHONPATH=/app
ENV OPERATIONS_DB=/app/data/operations.db
USER 1000

# Health check
HEALTHCHECK --interval=30s --timeout=3s \
  CMD python3 -c "import requests; requests.get('http://localhost/health')"

# Command to run the MCP server
CMD ["python3", "server.py"]

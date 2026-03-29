# MediaRadar MCP Server Dockerfile
# Build: docker build -t mediaradar-mcp:latest -f backend/services/mcp_service/Dockerfile .

FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for Playwright/爬虫
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    gnupg \
    ca-certificates \
    procps \
    && rm -rf /var/lib/apt/lists/*

# Install Playwright browsers (if needed by crawler)
RUN wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add - \
    && echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
    chromium \
    chromium-sandbox \
    fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for caching
COPY backend/services/mcp_service/requirements.txt /app/requirements.txt

# Install Python dependencies
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy backend source
COPY backend/ /app/backend/

# Set PYTHONPATH
ENV PYTHONPATH=/app/backend

# Expose HTTP port (for cloud deployment)
EXPOSE 8001

# Default: stdio mode for Claude Code
# To run HTTP mode: docker run -p 8001:8001 mediaradar-mcp:latest --transport http
CMD ["python", "backend/services/mcp_service/mcp_server.py"]

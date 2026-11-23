# Dockerfile for Self-Healing Cloud Network — Main Application
# This is a reference Dockerfile; the main app typically runs on the host
# while the individual cloud servers run via docker-compose.

FROM python:3.11-slim

LABEL maintainer="Self-Healing Cloud Network"
LABEL description="Main application for the Self-Healing Cloud Network"

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create logs directory
RUN mkdir -p logs

# Expose the Flask port
EXPOSE 5000

# Environment variables
ENV FLASK_HOST=0.0.0.0
ENV FLASK_PORT=5000
ENV PYTHONUNBUFFERED=1

# Health check
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -f http://localhost:5000/ || exit 1

# Run the application
CMD ["python", "app.py"]

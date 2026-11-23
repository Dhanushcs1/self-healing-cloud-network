# Dockerfile for Self-Healing Cloud Network - Main Application
# Runs all 3 simulated cloud servers and the central orchestrator dashboard.

FROM python:3.11-slim

LABEL maintainer="Self-Healing Cloud Network"
LABEL description="Self-Healing Cloud Network with Automatic Failure Detection and Dynamic Load Balancing"

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

# Expose ports
EXPOSE 5000

# Environment variables
ENV FLASK_HOST=0.0.0.0
ENV PORT=5000
ENV PYTHONUNBUFFERED=1

# Health check
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -f http://localhost:5000/ || exit 1

# Run the complete demo (spawns 3 servers + orchestrator)
CMD ["python", "start_demo.py"]

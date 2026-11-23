FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir flask psutil requests

COPY server.py .

ENV SERVER_NAME="Cloud Server" \
    SERVER_ID="1" \
    PORT="5000"

EXPOSE 5000

HEALTHCHECK --interval=10s --timeout=3s \
    CMD python -c "import requests; requests.get('http://localhost:5000/health')" || exit 1

CMD ["python", "server.py"]

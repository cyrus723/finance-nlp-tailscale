FROM python:3.11-slim

WORKDIR /app
COPY ../../requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV INGESTION_PORT=8001
EXPOSE 8001

# tailscaled runs as a sidecar — see docker-compose.tailscale.yml
CMD ["python", "main.py"]

FROM python:3.11-slim

RUN useradd -m appuser
WORKDIR /app
COPY ../../requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN mkdir -p /app/data && chown -R appuser:appuser /app
USER appuser

ENV STORAGE_PORT=8003
VOLUME ["/app/data"]
EXPOSE 8003

CMD ["python", "main.py"]

FROM python:3.11-slim

WORKDIR /app
COPY ../../requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV STORAGE_PORT=8003
VOLUME ["/app/data"]
EXPOSE 8003

CMD ["python", "main.py"]

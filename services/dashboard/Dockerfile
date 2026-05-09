FROM python:3.11-slim

RUN useradd -m appuser
WORKDIR /app
COPY ../../requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN chown -R appuser:appuser /app
USER appuser

ENV DASHBOARD_PORT=8000
EXPOSE 8000

CMD ["python", "main.py"]

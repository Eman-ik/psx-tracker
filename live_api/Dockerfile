FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOME=/data \
    TZ=Asia/Karachi

WORKDIR /app

COPY live_api/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY live_api /app/live_api
RUN mkdir -p /data/.psxdata/cache

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz').read()"

CMD ["uvicorn", "live_api.app.main:app", "--host", "0.0.0.0", "--port", "8000"]

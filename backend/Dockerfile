# HieraSync AI - backend image (API + engines + scheduler; serves the built SPA when STATIC_DIR is set)
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt ./
RUN pip install -r requirements.txt

COPY . .

# var/ holds the embedded document store and the notification outbox previews
RUN mkdir -p /app/var/outbox && \
    groupadd -r hiera && useradd -r -g hiera hiera && chown -R hiera:hiera /app
USER hiera

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8000/health',timeout=4).read()"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

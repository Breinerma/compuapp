FROM python:3.11-slim
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    TF_CPP_MIN_LOG_LEVEL=2 \
    DB_HOST=127.0.0.1 \
    DB_PORT=3306 \
    DB_NAME=naturalens \
    DB_USER=naturalens \
    DB_PASSWORD=JCMMCMAPbmamyma \
    COOKIE_SECURE=false \
    UPLOAD_DIR=/app/uploads
WORKDIR /app
# Copiar ANTES de instalar TensorFlow: VFS duplica el contenido de cada capa.
COPY . .
# Una sola capa grande; no añadir COPY ni RUN después de instalar dependencias.
RUN apt-get update && \
    apt-get install -y --no-install-recommends libgomp1 && \
    rm -rf /var/lib/apt/lists/* && \
    pip install --no-cache-dir -r requirements.txt && \
    useradd --create-home appuser && \
    mkdir -p /app/uploads && \
    chown -R appuser:appuser /app
USER appuser
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--proxy-headers", "--forwarded-allow-ips", "*"]

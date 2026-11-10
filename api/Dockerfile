FROM python:3.11-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 TF_CPP_MIN_LOG_LEVEL=2
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && useradd --create-home appuser
COPY --chown=appuser:appuser app ./app
COPY --chown=appuser:appuser model ./model
COPY --chown=appuser:appuser certs ./certs
RUN mkdir /app/uploads && chown appuser:appuser /app/uploads
USER appuser
# ECS/awsvpc: MySQL dentro de la misma tarea.
ENV DB_HOST=127.0.0.1 \
    DB_PORT=3306 \
    DB_NAME=naturalens \
    DB_USER=naturalens \
    DB_PASSWORD=JCMMCMAPbmamyma \
    COOKIE_SECURE=false \
    UPLOAD_DIR=/app/uploads
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--proxy-headers", "--forwarded-allow-ips", "*"]

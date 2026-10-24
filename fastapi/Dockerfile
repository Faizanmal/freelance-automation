FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app/fastapi:/app

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY fastapi/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY fastapi ./fastapi
COPY ai ./ai
COPY backend ./backend
COPY config ./config
COPY database ./database
COPY notifications ./notifications
COPY scrapers ./scrapers
COPY workers ./workers
COPY docker ./docker

RUN chmod +x /app/docker/cloud-run-entrypoint.sh \
    && addgroup --system app \
    && adduser --system --ingroup app app \
    && chown -R app:app /app
USER app

ENV SERVICE_ROLE=api
EXPOSE 8080

CMD ["/app/docker/cloud-run-entrypoint.sh"]

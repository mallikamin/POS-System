FROM python:3.12-slim AS builder
WORKDIR /build
RUN apt-get update && apt-get install -y --no-install-recommends gcc libpq-dev && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

FROM python:3.12-slim AS runtime
RUN groupadd -r posapp && useradd -r -g posapp -d /app -s /sbin/nologin posapp
RUN apt-get update && apt-get install -y --no-install-recommends libpq5 curl && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY --from=builder /install /usr/local
COPY --chown=posapp:posapp . .
RUN chmod +x scripts/*.sh
USER posapp
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 CMD curl -f http://localhost:8000/api/v1/health || exit 1
EXPOSE 8000
ENTRYPOINT ["scripts/start.sh"]
CMD ["--workers", "4"]

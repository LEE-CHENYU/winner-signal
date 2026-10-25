FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app/services/analysis
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg ca-certificates && rm -rf /var/lib/apt/lists/*
COPY services/analysis/requirements.lock /tmp/requirements.lock
RUN pip install --no-cache-dir -r /tmp/requirements.lock
COPY services/analysis/analysis services/analysis/analysis
COPY packages/contracts/schema.sql packages/contracts/schema.sql
COPY vendor/aeread vendor/aeread
COPY fixtures fixtures
COPY deploy/supervise.py deploy/supervise.py
CMD ["python", "deploy/supervise.py"]

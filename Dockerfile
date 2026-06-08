FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        curl \
        libcairo2 \
        libffi-dev \
        libgdk-pixbuf-2.0-0 \
        libpango-1.0-0 \
        libpangocairo-1.0-0 \
        shared-mime-info \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY api ./api
COPY workers ./workers
COPY migrations ./migrations
COPY alembic.ini ./alembic.ini
COPY celery_app.py ./celery_app.py

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir ".[dev]" flower

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]

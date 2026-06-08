#!/bin/bash
set -euo pipefail

echo "Starting DocuMind development services..."

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker not found. Install Docker Desktop: https://www.docker.com/products/docker-desktop/"
  exit 1
fi

cd "$(dirname "$0")/.."

docker compose -f infra/docker-compose.yml up -d postgres redis minio qdrant

echo "Waiting for services..."
sleep 6

docker exec "$(docker compose -f infra/docker-compose.yml ps -q postgres)" \
  pg_isready -U documind >/dev/null 2>&1 && echo "PostgreSQL: OK" || echo "PostgreSQL: WAIT"

docker exec "$(docker compose -f infra/docker-compose.yml ps -q redis)" \
  redis-cli ping >/dev/null 2>&1 && echo "Redis: OK" || echo "Redis: WAIT"

curl -sf http://localhost:9000/minio/health/live >/dev/null && echo "MinIO: OK" || echo "MinIO: WAIT"
curl -sf http://localhost:6333/healthz >/dev/null && echo "Qdrant: OK" || echo "Qdrant: WAIT"

echo "Running migrations..."
alembic upgrade head

echo "Checking model cache..."
make check-models

echo "Starting API..."
DOCUMINT_PROFILE=full DOCUMINT_DEV_MODE=true \
  uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload &

echo "Starting Celery worker..."
DOCUMINT_PROFILE=full celery -A celery_app worker --loglevel=info &

echo ""
echo "DocuMind running:"
echo "  API:     http://localhost:8000"
echo "  MinIO:   http://localhost:9001"
echo "  Qdrant:  http://localhost:6333/dashboard"
echo ""
echo "Test with: make smoke-test"

FROM python:3.12-slim-bookworm AS api
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements-deploy.lock ./
RUN pip install --no-cache-dir --require-hashes -r requirements-deploy.lock
COPY . .
ARG CORA_UID=1000
ARG CORA_GID=1000
RUN groupadd --gid ${CORA_GID} cora && useradd --uid ${CORA_UID} --gid cora --create-home cora
USER cora
CMD ["python", "-m", "uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--timeout-graceful-shutdown", "310"]

FROM api AS api-audio-cpu
USER root
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 && rm -rf /var/lib/apt/lists/*
COPY requirements-deploy-audio.lock ./
RUN pip install --no-cache-dir --require-hashes -r requirements-deploy-audio.lock
USER cora

FROM node:22-bookworm-slim AS frontend
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
ENV VITE_API_BASE_URL=/backend
RUN npm run build

FROM nginx:1.28-alpine AS web
COPY deploy/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=frontend /build/dist /usr/share/nginx/html

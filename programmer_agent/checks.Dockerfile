FROM python:3.12-slim-bookworm
WORKDIR /work
COPY requirements-deploy.lock /tmp/requirements-deploy.lock
RUN pip install --no-cache-dir --require-hashes -r /tmp/requirements-deploy.lock
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
USER 65534:65534
ENTRYPOINT ["python"]

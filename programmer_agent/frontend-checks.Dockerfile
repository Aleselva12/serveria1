FROM node:22-bookworm-slim
WORKDIR /opt/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --ignore-scripts && npm cache clean --force
ENV HOME=/tmp
USER 65534:65534
ENTRYPOINT ["node"]

FROM node:24.14.0-bookworm-slim AS frontend
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

FROM python:3.12.13-slim-bookworm AS app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app
COPY requirements.lock requirements-build.lock pyproject.toml README.md ./
RUN pip install --no-cache-dir -r requirements.lock -r requirements-build.lock
COPY src/ ./src/
RUN pip install --no-cache-dir --no-deps --no-build-isolation .
COPY --from=frontend /build/dist ./frontend/dist
COPY workbench.toml ./
COPY examples/ ./examples/
COPY deploy/ ./deploy/
RUN useradd --uid 10001 --create-home app && mkdir -p /app/.workbench && chown app:app /app/.workbench
USER app
EXPOSE 8080
CMD ["python", "-m", "graphragprov.workbench_api"]

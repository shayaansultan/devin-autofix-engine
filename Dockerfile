# ---------- Stage 1: build the React dashboard ----------
FROM node:20-alpine AS frontend
WORKDIR /frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npx vite build --outDir dist --emptyOutDir

# ---------- Stage 2: backend runtime (serves API + built dashboard) ----------
FROM python:3.12-slim AS runtime
WORKDIR /app
ENV PYTHONUNBUFFERED=1
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
COPY backend/pyproject.toml ./
RUN uv pip install --system --no-cache .
COPY backend/ ./
COPY --from=frontend /frontend/dist ./app/static
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

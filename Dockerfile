FROM node:22-alpine AS frontend
WORKDIR /build
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 RENTAL_ROOT=/app MPLCONFIGDIR=/tmp/matplotlib
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 && rm -rf /var/lib/apt/lists/*
COPY requirements.lock ./
RUN pip install --no-cache-dir --require-hashes -r requirements.lock
COPY pyproject.toml ./
COPY src/ src/
RUN pip install --no-cache-dir --no-deps . && useradd --uid 10001 --create-home rental
COPY artifacts/ artifacts/
COPY --from=frontend /build/dist/ frontend/dist/
USER rental
EXPOSE 8000
HEALTHCHECK --interval=20s --timeout=5s --start-period=30s --retries=3 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=4)"
CMD ["uvicorn", "hanoi_rentals.api:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]

FROM python:3.12-slim AS base

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libxml2 \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .
RUN pip install --no-cache-dir .

FROM base AS runtime

COPY src/ src/

EXPOSE 8000

CMD ["uvicorn", "clinguide.api.app:app", "--host", "0.0.0.0", "--port", "8000"]

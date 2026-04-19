FROM python:3.12-slim AS base

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libxml2 \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .
RUN pip install --no-cache-dir ".[ui]"

COPY src/ src/
COPY ui/ ui/
COPY eval/ eval/
COPY data/ data/

EXPOSE 8000 8501

CMD ["uvicorn", "clinguide.api.app:app", "--host", "0.0.0.0", "--port", "8000"]

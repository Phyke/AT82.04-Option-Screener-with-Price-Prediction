FROM python:3.14-slim

WORKDIR /app

# RUN apt-get update && apt-get install -y --no-install-recommends build-essential gcc \
#     && pip install --upgrade pip \
#     && apt-get purge -y --auto-remove build-essential gcc \
#     && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml /app/pyproject.toml

RUN pip install --no-cache-dir .

COPY . /app

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml README.md ./
COPY app ./app
COPY data ./data
COPY docs ./docs
COPY .env.example ./

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -e ".[dev]"

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]


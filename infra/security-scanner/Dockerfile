FROM python:3.12-slim
WORKDIR /app

# Install system deps and scanning tools + FastAPI runtime
RUN pip install --no-cache-dir \
    pip-audit \
    bandit \
    detect-secrets \
    fastapi \
    uvicorn \
    pydantic-settings \
    structlog \
    httpx \
    asyncpg \
    sqlalchemy \
    pyyaml

COPY . .
EXPOSE 8003
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8003"]

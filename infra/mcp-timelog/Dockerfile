FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml .
RUN pip install fastapi uvicorn
COPY main.py .
EXPOSE 8002
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8002"]

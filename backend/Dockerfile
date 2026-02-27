FROM python:3.12-slim

WORKDIR /app
ENV PYTHONPATH=/app

# Install uv
RUN pip install uv

# Copy dependency files first for layer caching
COPY pyproject.toml uv.lock* ./

# Install all dependencies (including dev deps for test runs)
RUN uv sync --frozen

# Patch copilotkit __init__.py: wrap CopilotKitMiddleware import in try/except
# because langchain.agents.middleware does not exist in LangChain < 0.4
RUN uv run python -c "\
import pathlib; \
f = pathlib.Path('.venv/lib/python3.12/site-packages/copilotkit/__init__.py'); \
c = f.read_text(); \
c = c.replace(\
    'from .copilotkit_lg_middleware import CopilotKitMiddleware', \
    'try:\n    from .copilotkit_lg_middleware import CopilotKitMiddleware\nexcept ImportError:\n    pass  # langchain.agents.middleware not available'\
); \
f.write_text(c); \
print('copilotkit patch applied')"

# Copy application code
COPY . .

CMD [".venv/bin/uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]

FROM python:3.11-slim

WORKDIR /app

# Copy requirements
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir pydantic fastapi uvicorn httpx tree-sitter tree-sitter-python qdrant-client numpy aiofiles python-dotenv

# Copy backend source
COPY backend/ ./backend/

WORKDIR /app/backend

# Expose port
EXPOSE 8000

# Run the app
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
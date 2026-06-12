FROM python:3.11-slim

WORKDIR /app

# Install system dependencies (optional, e.g. curl for healthcheck)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY backend/ ./backend/
COPY frontend/ ./frontend/
COPY data/ ./data/
RUN mkdir -p vector_db/indexes vector_db/metadata
COPY scripts/ ./scripts/

# Create environment variable defaults
ENV PORT=45123
ENV HOST=0.0.0.0
ENV CUDA_VISIBLE_DEVICES=""

EXPOSE 45123

# Start the uvicorn application after initializing the database
CMD ["sh", "-c", "if [ ! -f vector_db/indexes/faiss.index ]; then python scripts/build_index.py; fi && python -m backend.init_db && python -m uvicorn backend.main:app --host 0.0.0.0 --port 45123 --workers 1"]

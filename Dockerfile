# Single-stage Dockerfile — Python + pre-built frontend
# Why single stage: no Node.js needed; frontend is pure HTML/CSS/JS
# Run with: docker run -p 5001:5001 -e GEMINI_API_KEY=xxx dodge-ai

FROM python:3.11-slim

WORKDIR /app

# Install only what we need (Flask is the only non-stdlib dep)
RUN pip install flask==3.1.2 --no-cache-dir

# Copy application code
COPY backend/  ./backend/
COPY frontend/ ./frontend/

# Copy dataset and pre-build the SQLite DB at image build time
# This means the DB is baked into the image — no runtime ingestion needed
COPY dataset/  ./dataset/

# Build the DB during image build so startup is instant
RUN python3 backend/ingest.py

# Expose port
EXPOSE 5001

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# Start Flask with 4 threads for concurrent users
# For >50 concurrent users, switch to gunicorn: gunicorn -w 4 -t 60 backend.app:app
CMD ["python3", "backend/app.py"]

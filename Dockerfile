# Single-stage Dockerfile — Python + pre-built frontend
# Why single stage: no Node.js needed; frontend is pure HTML/CSS/JS
# Run with: docker run -p 5001:5001 -e OPENROUTER_API_KEY=xxx dodge-ai

FROM python:3.11-slim

WORKDIR /app

# Install dependencies
RUN pip install flask==3.1.2 gunicorn==21.2.0 --no-cache-dir

# Copy application code (files are at root, not in subdirectories)
COPY app.py llm.py graph.py guardrails.py ingest.py ./
COPY index.html ./
COPY requirements.txt ./

# Copy dataset for database ingestion
COPY dataset/ ./dataset/

# Build the database during image build so startup is instant
RUN python3 ingest.py

# Expose port
EXPOSE 5001

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# Start Flask with gunicorn on port 5001
# Railway will forward traffic to this port
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5001", "--timeout", "120", "app:app"]

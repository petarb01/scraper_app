# Backend Dockerfile with hot reload support
# Build context must be the project root (docker-compose sets this).
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copy root requirements (build context = project root)
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Install development dependencies for hot reload
RUN pip install --no-cache-dir watchdog

# Copy backend application code
COPY backend/ .

# Expose port
EXPOSE 5000

# Set environment variables
ENV FLASK_APP=app.py
ENV FLASK_ENV=development
ENV PYTHONUNBUFFERED=1

# Run with hot reload enabled
CMD ["python", "-m", "flask", "run", "--host=0.0.0.0", "--port=5000", "--reload"]

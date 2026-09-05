FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1
WORKDIR /app

# Install system dependencies for building some Python packages
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential gcc libpq-dev git curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY requirements.txt /app/requirements.txt
RUN pip install --upgrade pip \
    && pip install --no-cache-dir -r /app/requirements.txt

# Copy application code
COPY . /app

# Default command (gunicorn is used in docker-compose for production run)
CMD ["gunicorn", "printkiosk.wsgi:application", "--bind", "0.0.0.0:8000"]

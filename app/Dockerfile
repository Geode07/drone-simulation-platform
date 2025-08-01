# Use a lightweight Python base image
FROM python:3.11-slim

# Set workdir
WORKDIR /app

# Install system and Node.js dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    curl \
    gnupg \
 && rm -rf /var/lib/apt/lists/*

RUN curl -fsSL https://deb.nodesource.com/setup_18.x | bash - && \
    apt-get install -y nodejs

# ------------------------------
# Invalidate cache intelligently
# ------------------------------

# Copy package.json + lock file separately to optimize caching
COPY app/static/frontend/package*.json /app/static/frontend/

# Set working directory and install deps
WORKDIR /app/static/frontend
RUN npm install

# Now copy the rest of the frontend (JS, HTML, CSS, etc.)
COPY app/static/frontend /app/static/frontend

# Build the frontend
RUN npm run build

# ------------------------------
# Backend setup
# ------------------------------
WORKDIR /app
COPY app ./app
COPY app/requirements.txt ./requirements.txt
COPY wsgi.py ./wsgi.py

RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 8000
CMD ["gunicorn", "wsgi:application", "--bind", "0.0.0.0:8000"]
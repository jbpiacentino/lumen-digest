FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for build-essential if needed (for some AI libs)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# We don't COPY the code here because docker-compose mounts it via volumes for dev
# But for production, you would add: COPY . .

EXPOSE 8000


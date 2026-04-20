FROM python:3.12-slim

WORKDIR /app

# Install system deps for WeasyPrint, psycopg2, Bandit
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev libffi-dev libcairo2 libpango-1.0-0 libpangocairo-1.0-0 \
    libgdk-pixbuf-2.0-0 libxml2-dev libxslt1-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN grep -Ev "^(qdrant-client|sentence-transformers)==" requirements.txt > requirements.runtime.txt \
    && pip install --no-cache-dir -r requirements.runtime.txt

COPY . .

# Make startup script executable
RUN chmod +x start.sh

EXPOSE 8000
CMD ["bash", "start.sh"]

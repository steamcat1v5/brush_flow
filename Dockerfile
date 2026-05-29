# Stage 1: Build Frontend
FROM node:20-alpine AS frontend-builder
WORKDIR /frontend
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ ./
RUN npm run build

# Stage 2: Backend & Final Image
FROM python:3.11-slim
WORKDIR /app

# Install dependencies
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && \
    apt-get update && apt-get install -y --no-install-recommends tzdata && \
    rm -rf /var/lib/apt/lists/*

# Copy backend code
COPY backend/app ./app

# Copy built frontend from Stage 1
COPY --from=frontend-builder /frontend/dist ./frontend/dist

# Environment variables
ENV BF_DB_PATH=/app/data/brush_flow.db
ENV BF_HOST=0.0.0.0
ENV BF_PORT=8765

# Create data directory
RUN mkdir -p /app/data

# Use python -m app.main to respect settings.port and other env vars
CMD ["python", "-m", "app.main"]

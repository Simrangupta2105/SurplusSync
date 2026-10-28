# SurplusSync Backend Dockerfile
# Multi-stage build for production

# Stage 1: Build dependencies
FROM python:3.12-slim AS builder

# Set working directory
WORKDIR /build

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --user -r requirements.txt

# Stage 2: Runtime
FROM python:3.12-slim AS runtime

# Create non-root user for security
RUN groupadd -r django && useradd -r -g django django

# Set working directory
WORKDIR /app

# Create directories
RUN mkdir -p /app/staticfiles /app/media /app/logs && \
    chown -R django:django /app

# Copy from builder
COPY --from=builder /root/.local /home/django/.local
COPY --from=builder /build/requirements.txt .

# Ensure scripts in .local are usable
ENV PATH=/home/django/.local/bin:$PATH

# Copy application code
COPY . .

# Switch to non-root user
USER django

# Collect static files
RUN python manage.py collectstatic --noinput

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=15s --timeout=5s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request, sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/api/v1/health/', timeout=5).getcode() == 200 else 1)" || exit 1


# Run Django server
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]

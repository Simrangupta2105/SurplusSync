# SurplusSync ML Service Dockerfile
# Slim image with only inference dependencies

FROM python:3.12-slim AS runtime

# Create non-root user
RUN groupadd -r ml && useradd -r -g ml ml

WORKDIR /app

# Copy requirements first
COPY requirements.txt .

# Install minimal inference dependencies
RUN pip install --no-cache-dir \
    fastapi==0.115.0 \
    uvicorn==0.32.0 \
    pydantic==2.9.0 \
    numpy==1.26.4 \
    pandas==2.2.2 \
    scipy==1.14.1 \
    scikit-learn==1.5.1 \
    lightgbm==4.5.0 \
    joblib==1.4.2 \
    python-multipart==0.0.9


# Copy application code into /app/ml_service
COPY . /app/ml_service/

ENV PYTHONPATH=/app

# Switch to non-root user
USER ml

# Expose port
EXPOSE 8001

# Health check using python urllib
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8001/health')" || exit 1

# Run FastAPI
CMD ["uvicorn", "ml_service.app:app", "--host", "0.0.0.0", "--port", "8001"]


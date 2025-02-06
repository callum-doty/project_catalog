FROM python:3.9-slim

# Set environment variables
ENV PYTHONPATH=/app \
    FLASK_APP=wsgi.py \ 
    FLASK_ENV=production \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install system dependencies AS ROOT
RUN apt-get update && apt-get install -y \
    poppler-utils \
    gcc \
    python3-dev \
    libpoppler-dev \
    build-essential \
    tesseract-ocr \
    tesseract-ocr-eng \
    libtesseract-dev \
    libleptonica-dev \
    pkg-config \
    python3-magic \
    python3-dev \
    libmagic1 \
    zlib1g-dev \
    libmagic-dev \
    postgresql-client \
    libjpeg-dev \
    libopenjp2-7-dev \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Python packages AS ROOT
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt


RUN useradd -m appuser && chown -R appuser /app
USER appuser


COPY --chown=appuser . .


RUN mkdir -p uploads logs

EXPOSE 5000

CMD ["gunicorn", "--config", "gunicorn.conf.py", "wsgi:application"]
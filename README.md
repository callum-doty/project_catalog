# Project Catalog

A Flask-based document processing system that leverages AI for text extraction and analysis.

## Core Features

- PDF and Image Document Upload
- OCR Text Extraction (Tesseract)
- AI Analysis (Claude API)
- Document Storage (MinIO/S3)
- Asynchronous Processing (Celery)

## Tech Stack

- Backend: Flask
- Database: PostgreSQL
- Queue: Redis + Celery
- Storage: MinIO (S3-compatible)
- AI: Anthropic Claude API
- OCR: Tesseract

## Setup

### Prerequisites

- Docker
- Docker Compose
- Python 3.9+
- Claude API Key

### Installation

1. Clone the repository

```bash
git clone [your-repo-url]
```

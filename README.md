# Project Catalog - Document Processing System

## Overview

An intelligent document processing system for Axiom Strategies that leverages machine learning to enable sophisticated search capabilities across design assets. The system employs CNN technology to process both vectorized and non-vectorized text from Photoshop files and PDFs, supporting comprehensive asset management and retrieval.

## Architecture

The system is organized into several key components that work together to provide a complete document processing solution:

### Machine Learning Pipeline

The ML pipeline consists of two main components:

- CNN Module: Handles text detection and feature extraction from images
- Classification System: Categorizes documents based on extracted features

### Data Flow

1. Document Ingestion → PDF/PSD Processing → Feature Extraction → Classification → Storage
2. Search Queries → Feature Matching → Result Ranking → Response Generation

## Project Structure

```
project_catalog/
├── config/                     # Configuration files
│   ├── development.py         # Development settings
│   ├── production.py          # Production settings
│   └── test.py               # Test settings
├── src/
│   ├── ml/                    # Machine Learning components
│   │   ├── cnn/              # CNN implementation
│   │   │   ├── components/   # CNN building blocks
│   │   │   ├── models/      # Model definitions
│   │   │   └── utils/       # CNN utilities
│   │   ├── classification/   # Classification system
│   │   │   ├── components/  # Classification components
│   │   │   ├── models/     # Classification models
│   │   │   └── utils/      # Classification utilities
│   │   └── preprocessing/   # Data preprocessing
│   │       ├── text/       # Text processing
│   │       └── image/      # Image processing
│   ├── database/            # Database operations
│   │   ├── migrations/     # Database migrations
│   │   ├── models/        # SQLAlchemy models
│   │   └── repositories/  # Data access layer
│   ├── api/                # API implementation
│   │   ├── endpoints/     # Route handlers
│   │   ├── middleware/    # API middleware
│   │   └── schemas/      # Request/response schemas
│   └── frontend/          # Frontend application
│       ├── components/   # React components
│       ├── pages/       # Page definitions
│       ├── hooks/       # Custom React hooks
│       └── utils/       # Frontend utilities
├── docs/                 # Documentation
│   ├── projects/        # Project documentation
│   ├── technical/       # Technical documentation
│   └── user/           # User guides
├── models/             # Trained model artifacts
├── scripts/           # Utility scripts
├── tests/            # Test suite
│   ├── integration/  # Integration tests
│   ├── unit/        # Unit tests
│   └── fixtures/    # Test fixtures
└── utils/           # Shared utilities
```

## Setup and Installation

### Prerequisites

- Python 3.11+
- Poetry for dependency management
- PostgreSQL 13+
- Node.js 16+ (for frontend)
- GPU support (NVIDIA CUDA 11.0+)

### Development Environment Setup

1. Clone the repository:

```bash
git clone https://github.com/axiom-strategies/project-catalog.git
cd project_catalog
```

2. Install Python dependencies:

```bash
poetry install
```

3. Install frontend dependencies:

```bash
cd src/frontend
npm install
```

4. Set up environment variables:

```bash
cp config/development.py.example config/development.py
# Edit configuration with your settings
```

5. Initialize the database:

```bash
poetry run alembic upgrade head
```

### Running the Application

1. Start the API server:

```bash
poetry run uvicorn src.api.main:app --reload
```

2. Start the frontend development server:

```bash
cd src/frontend
npm run dev
```

## Development Workflow

### Code Quality

The project uses several tools to maintain code quality:

- Black for Python code formatting
- isort for import sorting
- flake8 for linting
- ESLint for JavaScript/TypeScript
- Prettier for frontend code formatting

### Testing

Run the test suite:

```bash
# Backend tests
poetry run pytest

# Frontend tests
cd src/frontend
npm test
```

### Database Migrations

Create a new migration:

```bash
poetry run alembic revision --autogenerate -m "description"
```

## API Documentation

API documentation is available at `/docs/api/` when running the development server.

## Performance Metrics

The system is designed to meet the following performance targets:

- Text extraction accuracy: >95%
- Classification accuracy: >90%
- Search response time: <2 seconds
- PDF processing time: <30 seconds per document

## Contributing

Please refer to our [Contributing Guide](docs/technical/CONTRIBUTING.md) for detailed information about our development process.

## License

Proprietary - Axiom Strategies

## Contact

- Project Lead: Callum Doty (doty.callum9@gmail.com)
- Project Manager: Chris D'Aniello

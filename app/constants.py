# app/constants.py
"""
This module serves as the single source of truth for all constants used 
throughout the application. Instead of defining constants in multiple files,
import them from here.

"""

# Document Processing Statuses
DOCUMENT_STATUSES = {
    'PENDING': 'PENDING',
    'PROCESSING': 'PROCESSING',
    'COMPLETED': 'COMPLETED',
    'FAILED': 'FAILED'
}

# Cache Timeouts (in seconds)
CACHE_TIMEOUTS = {
    'PREVIEW': 3600,  # 1 hour
    'SEARCH': 60,     # 1 minute
    'TAXONOMY': 300,  # 5 minutes
    'METRICS': 300,   # 5 minutes
    'DOCUMENT_COUNT': 60,  # 1 minute
    'HIERARCHICAL_KEYWORDS': 300,  # 5 minutes
}

# File Types
SUPPORTED_FILE_TYPES = {
    'IMAGES': ['.jpg', '.jpeg', '.png', '.gif'],
    'DOCUMENTS': ['.pdf'],
    'ALL': ['.jpg', '.jpeg', '.png', '.gif', '.pdf']
}

# Queue Names
QUEUE_NAMES = {
    'DOCUMENT_PROCESSING': 'document_processing',
    'ANALYSIS': 'analysis',
    'PREVIEWS': 'previews',
    'DEFAULT': 'celery'
}

# Search Types
SEARCH_TYPES = {
    'KEYWORD': 'keyword',
    'VECTOR': 'vector',
    'HYBRID': 'hybrid'
}

# API Rate Limits
API_RATE_LIMITS = {
    'CLAUDE': 10,  # requests per minute
    'OPENAI': 20   # requests per minute
}

# Default Settings
DEFAULTS = {
    'SEARCH_RESULTS_PER_PAGE': 12,
    'SORT_BY': 'upload_date',
    'SORT_DIRECTION': 'desc',
    'VECTOR_SIMILARITY_THRESHOLD': 0.7
}

# Model Settings
MODEL_SETTINGS = {
    'CLAUDE': {
        'MODEL': 'claude-3-opus-20240229',
        'MAX_TOKENS': 4096
    },
    'EMBEDDINGS': {
        'MODEL': 'text-embedding-3-small',
        'DIMENSIONS': 1536
    }
}

# Error Messages
ERROR_MESSAGES = {
    'FILE_NOT_FOUND': 'The requested file could not be found.',
    'PROCESSING_FAILED': 'Document processing failed. Please try again.',
    'INVALID_FILE_TYPE': 'Invalid file type. Please upload a PDF or supported image format.',
    'SERVICE_UNAVAILABLE': 'The service is temporarily unavailable. Please try again later.',
    'AUTHENTICATION_FAILED': 'Authentication failed. Please check your credentials.',
    'API_ERROR': 'Error communicating with external API. Please try again later.'
}
# config/settings.py
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Settings:
    # Flask Configuration
    FLASK_APP = os.getenv('FLASK_APP', 'wsgi.py')
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-key-please-change')
    
    # Database Configuration
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', 'postgresql://custom_user:strong_password@db:5432/catalog_db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # MinIO Configuration
    MINIO_URL = os.getenv('MINIO_URL', 'minio:9000')
    MINIO_ACCESS_KEY = os.getenv('MINIO_ACCESS_KEY', 'minioaccess')
    MINIO_SECRET_KEY = os.getenv('MINIO_SECRET_KEY', 'miniosecret')
    MINIO_BUCKET = os.getenv('MINIO_BUCKET', 'documents')
    
    # Celery Configuration
    broker_url = 'redis://redis:6379/0'  # lowercase for Celery
    result_backend = 'redis://redis:6379/0'  # lowercase for Celery
    task_serializer = 'json'  # lowercase for Celery
    result_serializer = 'json'  # lowercase for Celery
    accept_content = ['json']  # lowercase for Celery
    timezone = 'UTC'  # lowercase for Celery
    enable_utc = True  # lowercase for Celery
    task_routes = {  # lowercase for Celery
        'tasks.process_document': {'queue': 'document_processing'},
    }

    def init_app(self, app):
        # Initialize any specific settings if needed
        pass

# Create settings instance
settings = Settings()
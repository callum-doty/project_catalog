import os


class Config:
    """Base configuration."""

    SECRET_KEY = os.environ.get("SECRET_KEY")
    STATIC_FOLDER = "static"
    TEMPLATES_FOLDER = "templates"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    USE_MOCK_STORAGE = False  # Default to False


class ProductionConfig(Config):
    """Production configuration."""

    FLASK_ENV = "production"
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL")
    REDIS_URL = os.environ.get("REDIS_URL")
    # Add other production-specific settings from your render.yaml
    MINIO_INTERNAL_S3_HOST = os.environ.get("MINIO_INTERNAL_S3_HOST")
    MINIO_INTERNAL_S3_PORT = os.environ.get("MINIO_INTERNAL_S3_PORT")
    MINIO_PUBLIC_ENDPOINT = os.environ.get("MINIO_PUBLIC_ENDPOINT")
    MINIO_REGION = os.environ.get("MINIO_REGION")
    MINIO_ACCESS_KEY = os.environ.get("MINIO_ACCESS_KEY")
    MINIO_SECRET_KEY = os.environ.get("MINIO_SECRET_KEY")
    S3_BUCKET_NAME = os.environ.get("S3_BUCKET_NAME")


class DevelopmentConfig(Config):
    """Development configuration."""

    FLASK_ENV = "development"
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///../database/local_dev.db"
    REDIS_URL = "redis://localhost:6379/0"  # Local Redis instance
    USE_MOCK_STORAGE = False  # Use local file storage instead of MinIO
    # You can add other development-specific settings here
    S3_BUCKET_NAME = "local-documents"  # A local bucket name


class DockerDevelopmentConfig(Config):
    """Docker Development configuration."""

    FLASK_ENV = "development"
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL")
    REDIS_URL = os.environ.get("REDIS_URL")
    USE_MOCK_STORAGE = False
    MINIO_INTERNAL_S3_HOST = "minio"
    MINIO_INTERNAL_S3_PORT = "9000"
    MINIO_PUBLIC_ENDPOINT = "localhost:9000"
    MINIO_REGION = "us-east-1"
    MINIO_ACCESS_KEY = "minioaccess"
    MINIO_SECRET_KEY = "miniosecret"
    S3_BUCKET_NAME = "documents"

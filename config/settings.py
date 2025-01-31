import os

class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', 'defaultsecret')
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    MINIO_URL = os.getenv('MINIO_URL', 'minio:9000')
    MINIO_ACCESS_KEY = os.getenv('MINIO_ACCESS_KEY', 'minioaccess')
    MINIO_SECRET_KEY = os.getenv('MINIO_SECRET_KEY', 'miniosecret')
    MINIO_BUCKET = os.getenv('MINIO_BUCKET', 'documents')
    
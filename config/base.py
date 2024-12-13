# config/base.py
from pathlib import Path
import os

class BaseConfig:
    """
    Base configuration class that contains settings common to all environments.
    Other configuration classes will inherit from this one.
    """
    # Project structure
    PROJECT_ROOT = Path(__file__).parent.parent
    SRC_DIR = PROJECT_ROOT / 'src'
    
    # Application settings
    APP_NAME = 'Project Catalog'
    SECRET_KEY = os.getenv('SECRET_KEY', 'your-secret-key-here')
    
    # Flask settings
    FLASK_APP = 'src.api.app:create_app'
    STATIC_FOLDER = 'static'
    TEMPLATES_FOLDER = 'templates'
    
    # Database settings
    POSTGRES_HOST = os.getenv('POSTGRES_HOST', 'localhost')
    POSTGRES_PORT = int(os.getenv('POSTGRES_PORT', 5432))
    POSTGRES_DB = os.getenv('POSTGRES_DB', 'project_catalog')
    POSTGRES_USER = os.getenv('POSTGRES_USER', 'postgres')
    POSTGRES_PASSWORD = os.getenv('POSTGRES_PASSWORD', 'postgres')
    
    @property
    def SQLALCHEMY_DATABASE_URI(self):
        """Construct database URI from components"""
        return f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@" \
               f"{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
    
    # Dropbox settings
    DROPBOX_APP_KEY = os.getenv('DROPBOX_APP_KEY')
    DROPBOX_APP_SECRET = os.getenv('DROPBOX_APP_SECRET')
    DROPBOX_REFRESH_TOKEN = os.getenv('DROPBOX_REFRESH_TOKEN')
    
    # CNN settings
    MODEL_DIR = PROJECT_ROOT / 'models'
    RESNET_MODEL_PATH = MODEL_DIR / 'resnet_model.pth'
    CNN_BATCH_SIZE = 32
    CNN_IMAGE_SIZE = (224, 224)  # ResNet default input size
    CNN_LEARNING_RATE = 0.001
    
    # File handling
    UPLOAD_FOLDER = PROJECT_ROOT / 'data' / 'uploads'
    ALLOWED_EXTENSIONS = {'pdf', 'psd', 'ai', 'jpg', 'png'}
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size
    
    # Cache settings
    CACHE_TYPE = 'simple'
    CACHE_DEFAULT_TIMEOUT = 300
    
    # Security settings
    SESSION_COOKIE_SECURE = True
    REMEMBER_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_HTTPONLY = True

# config/development.py
from .base import BaseConfig

class DevelopmentConfig(BaseConfig):
    """Development configuration."""
    
    DEBUG = True
    TESTING = False
    
    # Override database for development
    POSTGRES_DB = 'project_catalog_dev'
    
    # Development-specific settings
    FLASK_ENV = 'development'
    TEMPLATES_AUTO_RELOAD = True
    
    # Disable HTTPS requirement in development
    SESSION_COOKIE_SECURE = False
    REMEMBER_COOKIE_SECURE = False
    
    # CNN development settings
    CNN_BATCH_SIZE = 8  # Smaller batch size for faster iteration
    
    # Enable SQLAlchemy debug mode
    SQLALCHEMY_ECHO = True
    
    # File upload directory for development
    UPLOAD_FOLDER = BaseConfig.PROJECT_ROOT / 'data' / 'dev_uploads'

# config/production.py
from .base import BaseConfig

class ProductionConfig(BaseConfig):
    """Production configuration."""
    
    DEBUG = False
    TESTING = False
    
    # Production database should be configured via environment variables
    
    # Production-specific settings
    FLASK_ENV = 'production'
    TEMPLATES_AUTO_RELOAD = False
    
    # Enhanced security settings for production
    CSRF_ENABLED = True
    CSRF_SESSION_KEY = os.getenv('CSRF_SESSION_KEY')
    
    # Production caching
    CACHE_TYPE = 'redis'
    CACHE_REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
    CACHE_REDIS_PORT = int(os.getenv('REDIS_PORT', 6379))
    
    # Production CNN settings
    CNN_BATCH_SIZE = 64  # Larger batch size for production
    
    # Logging
    LOG_LEVEL = 'INFO'
    LOG_TO_STDOUT = os.getenv('LOG_TO_STDOUT', 'false').lower() == 'true'

# config/test.py
from .base import BaseConfig

class TestConfig(BaseConfig):
    """Testing configuration."""
    
    DEBUG = False
    TESTING = True
    
    # Test database
    POSTGRES_DB = 'project_catalog_test'
    
    # Disable CSRF tokens in tests
    WTF_CSRF_ENABLED = False
    
    # Test-specific settings
    PRESERVE_CONTEXT_ON_EXCEPTION = False
    
    # Smaller CNN batch size for testing
    CNN_BATCH_SIZE = 2
    
    # Test upload directory
    UPLOAD_FOLDER = BaseConfig.PROJECT_ROOT / 'data' / 'test_uploads'

# config/__init__.py
import os

# Map environment names to config classes
config = {
    'development': 'config.development.DevelopmentConfig',
    'production': 'config.production.ProductionConfig',
    'test': 'config.test.TestConfig',
    'default': 'config.development.DevelopmentConfig'
}

def get_config():
    """
    Get the configuration class based on the FLASK_ENV environment variable.
    Returns the development config by default.
    """
    env = os.getenv('FLASK_ENV', 'development')
    return config.get(env, config['default'])
# src/catalog/__init__.py
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_caching import Cache
from flask_wtf.csrf import CSRFProtect
import os

# Create extension instances
db = SQLAlchemy()
migrate = Migrate()
cache = Cache()
csrf = CSRFProtect()


def create_app(test_config=None):
    """Application factory pattern for Flask app"""

    # Create and configure the app
    template_dir = os.path.join(os.path.dirname(
        os.path.abspath(__file__)), 'templates')
    static_dir = os.path.join(os.path.dirname(
        os.path.abspath(__file__)), 'static')

    app = Flask(__name__,
                template_folder=template_dir,
                static_folder=static_dir)

    # Load default configuration
    app.config.from_mapping(
        SECRET_KEY=os.environ.get('SECRET_KEY', 'dev-key-please-change'),
        SQLALCHEMY_DATABASE_URI=os.environ.get(
            'DATABASE_URL', 'postgresql://custom_user:strong_password@db:5432/catalog_db'),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        CACHE_TYPE='redis',
        CACHE_REDIS_URL=os.environ.get('REDIS_URL', 'redis://redis:6379/0'),
        CACHE_DEFAULT_TIMEOUT=300,
        WTF_CSRF_CHECK_DEFAULT=False,
        WTF_CSRF_TIME_LIMIT=None,
        WTF_CSRF_SSL_STRICT=False,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE='Lax',
    )

    # Detect Railway.app deployment
    if 'RAILWAY_ENVIRONMENT' in os.environ:
        app.config['SESSION_COOKIE_SECURE'] = True
        app.config['PREFERRED_URL_SCHEME'] = 'https'

    # Initialize extensions with the app
    db.init_app(app)
    migrate.init_app(app, db)
    cache.init_app(app)
    csrf.init_app(app)

    # Register blueprints
    with app.app_context():
        try:
            # Import blueprints here to avoid circular imports
            from src.catalog.web.main_routes import main_routes
            from src.catalog.web.search_routes import search_routes

            app.register_blueprint(main_routes)
            app.register_blueprint(search_routes, url_prefix='/search')
        except Exception as e:
            app.logger.error(f"Error registering blueprints: {str(e)}")
            raise

    # Add middleware for security headers
    @app.after_request
    def add_security_headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'

        if 'RAILWAY_ENVIRONMENT' in os.environ or os.environ.get('BEHIND_PROXY', 'false').lower() == 'true':
            response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'

        return response

    # Add middleware for handling proxies
    @app.before_request
    def handle_proxy():
        if 'RAILWAY_ENVIRONMENT' in os.environ or os.environ.get('BEHIND_PROXY', 'false').lower() == 'true':
            from flask import request
            if 'X-Forwarded-Proto' in request.headers:
                if request.headers['X-Forwarded-Proto'] == 'https':
                    request.environ['wsgi.url_scheme'] = 'https'

    return app

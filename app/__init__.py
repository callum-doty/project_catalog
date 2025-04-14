# app/__init__.py
from flask import Flask, session, request
from flask_wtf.csrf import CSRFProtect
from app.extensions import db, migrate, cache
import os
from flask_caching import Cache

csrf = CSRFProtect()

def create_app():
    template_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')
    static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')
    
    app = Flask(__name__,
                template_folder=template_dir,
                static_folder=static_dir)
    
    # Set configuration
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'generate_a_secure_random_key')
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    app.config['CACHE_TYPE'] = 'redis'
    app.config['CACHE_REDIS_URL'] = os.environ.get('REDIS_URL', 'redis://redis:6379/0')
    app.config['CACHE_DEFAULT_TIMEOUT'] = 300  # 5 minutes default timeout
    cache.init_app(app)
    
    # CSRF Configuration
    app.config['WTF_CSRF_CHECK_DEFAULT'] = False  # Allow non-CSRF protected views by default
    app.config['WTF_CSRF_TIME_LIMIT'] = None      # No time limit for CSRF tokens
    app.config['WTF_CSRF_SSL_STRICT'] = False     # Don't require HTTPS for CSRF
    
    # Detect Railway.app deployment
    is_railway = 'RAILWAY_ENVIRONMENT' in os.environ
    
    # Cookie Security Settings
    # On Railway.app, always use secure cookies
    app.config['SESSION_COOKIE_SECURE'] = is_railway or os.environ.get('SECURE_COOKIES', 'false').lower() == 'true'
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
    
    # Railway.app provides HTTPS, so set preferred URL scheme accordingly
    if is_railway or os.environ.get('BEHIND_PROXY', 'false').lower() == 'true':
        app.config['PREFERRED_URL_SCHEME'] = 'https'
    
    # Initialize extensions
    csrf.init_app(app)
    db.init_app(app)
    migrate.init_app(app, db)
    
    # Register blueprints
    with app.app_context():
        from app.routes.main_routes import main_routes
        app.register_blueprint(main_routes)
        
        # Add security headers middleware
        @app.after_request
        def add_security_headers(response):
            # Basic security headers
            response.headers['X-Content-Type-Options'] = 'nosniff'
            response.headers['X-Frame-Options'] = 'SAMEORIGIN'
            
            # Set HSTS header for HTTPS environments
            if is_railway or os.environ.get('BEHIND_PROXY', 'false').lower() == 'true':
                response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
            
            return response
        
        # Add railway-specific middleware to handle proxies
        @app.before_request
        def handle_railway_proxy():
            # Check for Railway or other proxied environments
            if is_railway or os.environ.get('BEHIND_PROXY', 'false').lower() == 'true':
                # Trust the Railway.app proxy to set correct scheme and host
                if 'X-Forwarded-Proto' in request.headers:
                    if request.headers['X-Forwarded-Proto'] == 'https':
                        request.environ['wsgi.url_scheme'] = 'https'
    
    return app
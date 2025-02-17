# app/__init__.py

from flask import Flask
from flask_wtf.csrf import CSRFProtect
from app.extensions import db, migrate
from config.settings import settings
import os

csrf = CSRFProtect()

def create_app():
    """Create Flask application"""
    app = Flask(__name__)
    
    # Load config
    app.config.from_object(settings)
    settings.init_app(app)
    
    # Ensure template and static directories are set correctly
    app.template_folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')
    app.static_folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')
    
    # Set WTF CSRF config
    app.config['WTF_CSRF_CHECK_DEFAULT'] = False
    app.config['WTF_CSRF_TIME_LIMIT'] = None
    
    # Initialize extensions
    csrf.init_app(app)
    db.init_app(app)
    migrate.init_app(app, db)
    
    # Register blueprints
    with app.app_context():
        from app.routes.main_routes import main_routes
        app.register_blueprint(main_routes)
    
    return app
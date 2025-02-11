# app/__init__.py

from flask import Flask
from flask_wtf.csrf import CSRFProtect
from app.extensions import db, migrate
from config.settings import settings
import os

csrf = CSRFProtect()

def create_app():
    template_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')
    static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')
    
    app = Flask(__name__,
                template_folder=template_dir,
                static_folder=static_dir)
    
    # Load config
    app.config.from_object(settings)
    settings.init_app(app)
    
    # Set WTF CSRF config
    app.config['WTF_CSRF_CHECK_DEFAULT'] = False  # Disable global CSRF
    app.config['WTF_CSRF_TIME_LIMIT'] = None  # No time limit
    
    # Initialize CSRF protection
    csrf.init_app(app)
    
    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    
    # Register blueprints
    with app.app_context():
        from app.routes.main_routes import main_routes
        app.register_blueprint(main_routes)
    
    return app
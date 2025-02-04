# app/__init__.py

from flask import Flask
from app.extensions import db, migrate
from config.settings import settings
import os

def create_app():
    template_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')
    static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')
    
    app = Flask(__name__,
                template_folder=template_dir,
                static_folder=static_dir)
    
    # Load config
    app.config.from_object(settings)
    settings.init_app(app)
    
    # Ensure critical configs are set
    if not app.config.get('SQLALCHEMY_DATABASE_URI'):
        raise RuntimeError(
            'SQLALCHEMY_DATABASE_URI is not set. '
            'Please check your environment variables and configuration.'
        )
    
    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    
    # Register blueprints
    with app.app_context():
        from app.routes.main_routes import main_routes
        app.register_blueprint(main_routes)
    
    return app
# app/factory.py

from flask import Flask
from app.extensions import db, migrate
from celery import Celery
from config import settings
import os
from dotenv import load_dotenv

def create_app():
    """Create Flask application"""
    app = Flask(__name__,
                template_folder=os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates'),
                static_folder=os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static'))
    
    load_dotenv()
    
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-key-please-change')
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    
    # Register blueprints
    with app.app_context():
        from app.routes.main_routes import main_routes
        app.register_blueprint(main_routes)
    
    return app

def create_celery():
    """Create Celery application"""
    celery = Celery('tasks')
    
    # Configure Celery
    celery.conf.update(
        broker_url='redis://redis:6379/0',
        result_backend='redis://redis:6379/0',
        task_serializer='json',
        accept_content=['json'],
        result_serializer='json',
        timezone='UTC',
        enable_utc=True,
        imports=['tasks.document_tasks'],
        task_routes={
            'tasks.process_document': {'queue': 'document_processing'},
        }
    )
    
    return celery

# Create the applications
flask_app = create_app()
celery_app = create_celery()

# Configure Celery to work with Flask context
class FlaskTask(celery_app.Task):
    def __call__(self, *args, **kwargs):
        with flask_app.app_context():
            return self.run(*args, **kwargs)

celery_app.Task = FlaskTask
# app/flask_app.py

from flask import Flask
from app.extensions import db, migrate
from dotenv import load_dotenv
import os

def create_app():
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

# Create the Flask application instance
flask_app = create_app()
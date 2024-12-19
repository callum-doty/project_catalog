from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from config.settings import Config

db = SQLAlchemy()
migrate = Migrate()


def create_app(config_class=Config):
    """Create and configure the Flask application"""
    app = Flask(__name__,
                template_folder='../frontend/templates',
                static_folder='../frontend/static')

    # Load configuration
    app.config.from_object(config_class)

    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)

    # Register blueprints
    from src.api.endpoints.main import bp as main_bp
    app.register_blueprint(main_bp)

    return app

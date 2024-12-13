from flask import Flask
from config import get_config
from dotenv import load_dotenv

def create_app(config_object=None):
    """Application factory."""
    load_dotenv()
    
    app = Flask(__name__)
    
    # Load config
    if config_object is None:
        config_object = get_config()
    app.config.from_object(config_object)
    
    # Initialize extensions
    init_extensions(app)
    
    # Register blueprints
    register_blueprints(app)
    
    return app
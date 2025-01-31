from flask import Flask
from app.extensions import db, migrate
from dotenv import load_dotenv

load_dotenv()  # Load environment variables

def create_app():
    app = Flask(__name__)
    app.config.from_object('config.settings')

    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)

    # Import models within context
    with app.app_context():
        from app.models import Document, BatchJob, LLMAnalysis, ExtractedText, DesignElement, Classification, LLMKeyword, Client

    # Register blueprints
    from app.routes.main_routes import main_bp
    app.register_blueprint(main_bp)

    return app

app = create_app()
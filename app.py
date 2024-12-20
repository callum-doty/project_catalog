# app.py
from flask import Flask, jsonify, request, render_template, session
from flask_migrate import Migrate
from flask_cors import CORS
from config import Config
from src.database.db import db
from src.database.models import Document
from src.integrations.dropbox_handler import DropboxHandler
from dropbox import Dropbox
from dropbox.oauth import DropboxOAuth2FlowNoRedirect
from datetime import datetime
from src.tasks.sync_manager import DropboxSyncManager
import os
import logging

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Create Flask app
app = Flask(__name__, template_folder='src/frontend/templates')
app.config.from_object(Config)

# Configure CORS properly
CORS(app, resources={
    r"/*": {
        "origins": ["http://localhost:5001", "http://127.0.0.1:5001"],
        "methods": ["GET", "POST", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"]
    }
})

# Initialize extensions
db.init_app(app)
migrate = Migrate(app, db)
sync_manager = DropboxSyncManager(app)

# Ensure secret key is set for sessions
app.secret_key = os.getenv('SECRET_KEY', 'dev-secret-key')


@app.route('/')
def home():
    return jsonify({"message": "API is running"}), 200


@app.route('/dropbox/auth')
def dropbox_auth():
    try:
        auth_flow = DropboxOAuth2FlowNoRedirect(
            os.getenv('DROPBOX_APP_KEY'),
            os.getenv('DROPBOX_APP_SECRET'),
            token_access_type='offline'
        )
        # Get authorization URL
        authorize_url = auth_flow.start()

        return jsonify({
            "message": "Please visit this URL to authorize the application",
            "authorize_url": authorize_url
        })
    except Exception as e:
        logger.error(f"Error starting Dropbox OAuth flow: {str(e)}")
        return jsonify({"error": str(e)}), 500


@app.route('/dropbox/auth/finish', methods=['POST'])
def dropbox_auth_finish():
    try:
        auth_code = request.json.get('code')
        if not auth_code:
            return jsonify({"error": "No authorization code provided"}), 400

        # Create a new flow for finishing the auth process
        auth_flow = DropboxOAuth2FlowNoRedirect(
            os.getenv('DROPBOX_APP_KEY'),
            os.getenv('DROPBOX_APP_SECRET'),
            token_access_type='offline'
        )

        # Exchange auth code for refresh token
        oauth_result = auth_flow.finish(auth_code)

        # Store refresh token in environment or database
        refresh_token = oauth_result.refresh_token

        return jsonify({
            "message": "Successfully authorized. Add this refresh_token to your .env file",
            "refresh_token": refresh_token
        })

    except Exception as e:
        logger.error(f"Error completing Dropbox OAuth flow: {str(e)}")
        return jsonify({"error": str(e)}), 500


@app.route('/test-dropbox')
def test_dropbox():
    try:
        logger.debug("Starting Dropbox test")
        handler = DropboxHandler()

        # Test connection
        logger.debug("Testing connection...")
        if not handler.test_connection():
            logger.error("Failed Dropbox connection test")
            return jsonify({"error": "Failed to connect to Dropbox"}), 500

        # Test listing files
        folder_path = os.getenv('DROPBOX_FOLDER_PATH', '')
        logger.debug(f"Testing file listing in path: {folder_path}")
        files = handler.list_documents(folder_path)

        return jsonify({
            "status": "success",
            "folder_path": folder_path,
            "files": [{
                "name": f.name,
                "size": f.size,
                "modified": f.server_modified.isoformat(),
                "path": f.path_display
            } for f in files]
        }), 200

    except Exception as e:
        logger.error(f"Error in test-dropbox route: {str(e)}")
        return jsonify({"error": str(e)}), 500


@app.route('/sync', methods=['POST'])
def trigger_sync():
    try:
        sync_manager.force_sync()
        return jsonify({"message": "Sync triggered successfully"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Add a route to check sync status


@app.route('/sync/status', methods=['GET'])
def get_sync_status():
    try:
        # Get the most recent documents
        recent_docs = Document.query.order_by(
            Document.upload_date.desc()).limit(10).all()

        return jsonify({
            "total_documents": Document.query.count(),
            "recent_syncs": [{
                "filename": doc.filename,
                "status": doc.status,
                "upload_date": doc.upload_date.isoformat() if doc.upload_date else None,
                "file_size": doc.file_size
            } for doc in recent_docs]
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Error handlers


@app.errorhandler(404)
def not_found_error(error):
    logger.error(f"Route not found: {request.url}")
    return jsonify({"error": "Not found"}), 404


@app.errorhandler(500)
def internal_error(error):
    logger.error(f"Internal server error: {str(error)}")
    return jsonify({"error": "Internal server error"}), 500


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)

# src/wsgi.py
import os
import sys
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Simple healthcheck application


def health_app(environ, start_response):
    status = '200 OK'
    headers = [('Content-type', 'text/plain')]
    start_response(status, headers)
    return [b'OK']


# Try to load the main application if possible
try:
    # Import the Flask application with correct import path
    from src.catalog import create_app

    # Create the Flask application
    flask_app = create_app()

    # Add a health check route
    @flask_app.route('/health')
    def health():
        return 'OK'

    # Set the main application
    application = flask_app

    logger.info("Flask application initialized successfully")

except Exception as e:
    # Log the error but don't crash
    logger.error(
        f"Failed to initialize Flask application: {str(e)}", exc_info=True)

    # Fallback to a simple WSGI app that just returns health checks
    def application(environ, start_response):
        if environ['PATH_INFO'] == '/health':
            return health_app(environ, start_response)

        # Anything else returns a 503 Service Unavailable
        status = '503 Service Unavailable'
        headers = [('Content-type', 'text/plain')]
        start_response(status, headers)
        return [b'Application initialization failed']

# Run the application if executed directly
if __name__ == '__main__':
    # Create and run the app
    app = create_app()
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))

# wsgi.py

import os
import sys
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Print debugging information
logger.info("Python version: %s", sys.version)
logger.info("Current working directory: %s", os.getcwd())
logger.info("Contents of current directory: %s", os.listdir('.'))

try:
    # Simple health check endpoint for Railway
    class HealthApp:
        def __call__(self, environ, start_response):
            if environ['PATH_INFO'] == '/health':
                start_response('200 OK', [('Content-Type', 'text/plain')])
                return [b'Healthy']
            
            # For all other requests, use the actual application
            return self.app(environ, start_response)
    
    # Import the Flask application
    from app import create_app
    
    # Create the Flask application
    flask_app = create_app()
    
    # Add a health check route
    @flask_app.route('/health')
    def health():
        return 'Healthy'
    
    # Get the WSGI application
    application = flask_app
    
    # Wrap with health check
    # application = HealthApp().__call__
    
    logger.info("Application initialized successfully")
    
except Exception as e:
    logger.error("Error initializing application: %s", str(e), exc_info=True)
    
    # Provide a minimal application for health checks even if the main app fails
    def application(environ, start_response):
        if environ['PATH_INFO'] == '/health':
            start_response('200 OK', [('Content-Type', 'text/plain')])
            return [b'Healthy but application failed to initialize']
        
        start_response('500 Internal Server Error', [('Content-Type', 'text/plain')])
        return [f'Application failed to initialize: {str(e)}'.encode()]

# Run the Flask application if executed directly
if __name__ == '__main__':
    from app import create_app
    app = create_app()
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
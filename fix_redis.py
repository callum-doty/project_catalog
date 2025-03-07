# fix_redis.py - Must be imported BEFORE any Celery-related imports

import os
import logging

logger = logging.getLogger(__name__)

def fix_redis_url():
    """
    Ensure Redis URL is properly set in the environment
    This must be called before any Celery imports
    """
    # Check for Redis URL
    redis_url = os.environ.get('REDIS_URL')
    
    if redis_url:
        # Print a sanitized version of the URL
        safe_url = redis_url.replace('redis://', 'redis://****:****@')
        logger.info(f"Found Redis URL: {safe_url}")
        
        # Explicitly set all needed environment variables
        os.environ['CELERY_BROKER_URL'] = redis_url
        os.environ['CELERY_RESULT_BACKEND'] = redis_url
        os.environ['broker_url'] = redis_url
        os.environ['result_backend'] = redis_url
        
        # Return True to indicate success
        return True
    else:
        logger.warning("No Redis URL found in environment variables!")
        return False

# Call the function immediately when imported
fix_redis_url()
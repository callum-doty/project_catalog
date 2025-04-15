# app/utils.py

from functools import wraps
from flask import current_app
import time
from app import db
import concurrent.futures

def monitor_query(f):
    """Decorator to log if a function takes longer than 500ms"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        start_time = time.time()
        try:
            return f(*args, **kwargs)
        finally:
            query_time = time.time() - start_time
            if query_time > 0.5:  # Log queries taking more than 500ms
                current_app.logger.warning(f"Slow query: {f.__name__} took {query_time:.2f}s")
    return decorated_function


def document_has_column(model, column_name):
    """Check if a column exists in a SQLAlchemy model"""
    return hasattr(model, column_name)

def search_with_timeout(query_fn, timeout_sec=5):
    """Run a query-producing function with a timeout in a background thread"""
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(query_fn)
            return future.result(timeout=timeout_sec)
    except Exception as e:
        current_app.logger.error(f"Query timeout or error: {str(e)}")
        return []

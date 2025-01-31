# wsgi.py

import os
print("Current working directory:", os.getcwd())
print("Python path:", os.environ.get('PYTHONPATH'))
print("Contents of current directory:", os.listdir('.'))

from app import create_app
application = create_app()
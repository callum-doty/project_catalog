# wsgi.py

import os
import sys

print("Python version:", sys.version)
print("Current working directory:", os.getcwd())
print("Contents of current directory:", os.listdir('.'))
print("Environment variables:", {k: v for k, v in os.environ.items() if 'SECRET' not in k.upper()})

from app import create_app
application = create_app()

if __name__ == '__main__':
    application.run()
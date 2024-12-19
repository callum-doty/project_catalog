# manage.py

# Import Flask's command line interface tools
from flask import Flask
from flask.cli import FlaskGroup

# Import our application instance
from app import app

# Create a CLI group for our application
cli = FlaskGroup(app)

if __name__ == '__main__':
    cli()

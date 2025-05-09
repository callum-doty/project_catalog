# migrate.py
import os
import sys
from flask_migrate import stamp, migrate, upgrade


def run_migrations():
    try:
        print("Starting database migration process...")
        print(f"Current directory: {os.getcwd()}")
        print(f"Python version: {sys.version}")

        # Import app inside function to ensure environment is set up
        from src.catalog import create_app
        app = create_app()

        with app.app_context():
            print("Stamping migration head...")
            stamp()
            print("Generating migrations...")
            migrate()
            print("Applying migrations...")
            upgrade()
            print("Migration completed successfully!")

    except Exception as e:
        print(f"Migration failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(run_migrations())

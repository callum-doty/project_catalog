import os


def fix_env_vars():
    """Fix environment variables that might be incorrectly formatted."""
    # Check if DATABASE_URL is literally ${DATABASE_URL}
    if os.environ.get('DATABASE_URL') == '${DATABASE_URL}':
        # Try to build it from individual Postgres variables
        user = os.environ.get('POSTGRES_USER', 'custom_user')
        password = os.environ.get('POSTGRES_PASSWORD', 'strong_password')
        host = os.environ.get('POSTGRES_HOST', 'db')
        port = os.environ.get('POSTGRES_PORT', '5432')
        database = os.environ.get('POSTGRES_DATABASE', 'catalog_db')

        # Set the DATABASE_URL
        db_url = f"postgresql://{user}:{password}@{host}:{port}/{database}"
        os.environ['DATABASE_URL'] = db_url
        os.environ['SQLALCHEMY_DATABASE_URI'] = db_url

        print(f"Set DATABASE_URL to {db_url}")

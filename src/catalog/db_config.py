# src/catalog/db_config.py
import os

# Fixed Railway PostgreSQL connection details
RAILWAY_DB = {
    'host': 'shinkansen.proxy.rlwy.net',
    'port': '52940',
    'database': 'railway',
    'user': 'postgres',
    'password': 'ktUhwMMfeuiDxLHwSNLoEwGfPoenjCZI'
}


def get_db_uri():
    """Get the database URI, with fallback to fixed Railway connection"""
    # First try environment variables
    database_url = os.environ.get('DATABASE_URL')

    # Replace 'postgres://' with 'postgresql://' if needed (SQLAlchemy >= 1.4)
    if database_url and database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql://', 1)

    # If no DATABASE_URL in environment, use fixed Railway connection
    if not database_url and os.environ.get('RAILWAY_ENVIRONMENT'):
        database_url = f"postgresql://{RAILWAY_DB['user']}:{RAILWAY_DB['password']}@{RAILWAY_DB['host']}:{RAILWAY_DB['port']}/{RAILWAY_DB['database']}"
        print(
            f"Using hardcoded Railway database URI: postgresql://{RAILWAY_DB['user']}:****@{RAILWAY_DB['host']}:{RAILWAY_DB['port']}/{RAILWAY_DB['database']}")

    return database_url

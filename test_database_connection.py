#!/usr/bin/env python
"""
Script to test database connection and diagnose issues.
This script attempts to connect to the database using the configured connection string
and provides detailed error information if the connection fails.
"""

import os
import sys
import traceback
from urllib.parse import urlparse

# Try to import SQLAlchemy
try:
    from sqlalchemy import create_engine, text
    from sqlalchemy.exc import SQLAlchemyError

    HAVE_SQLALCHEMY = True
except ImportError:
    HAVE_SQLALCHEMY = False

# Try to import psycopg2
try:
    import psycopg2

    HAVE_PSYCOPG2 = True
except ImportError:
    HAVE_PSYCOPG2 = False


def get_database_uri():
    """Get the database URI from environment variables."""
    # First check for DATABASE_URL (Render's standard)
    database_url = os.environ.get("DATABASE_URL")
    if database_url:
        # Render provides PostgreSQL connection strings that begin with postgres://
        # but SQLAlchemy requires postgresql://
        if database_url.startswith("postgres://"):
            database_url = database_url.replace("postgres://", "postgresql://", 1)
        return database_url

    # Check for SQLALCHEMY_DATABASE_URI (Flask-SQLAlchemy's standard)
    sqlalchemy_uri = os.environ.get("SQLALCHEMY_DATABASE_URI")
    if sqlalchemy_uri:
        return sqlalchemy_uri

    # Try to build from components
    db_user = os.environ.get("DB_USER") or os.environ.get("POSTGRES_USER")
    db_password = os.environ.get("DB_PASSWORD") or os.environ.get("POSTGRES_PASSWORD")
    db_host = os.environ.get("DB_HOST", "localhost")
    db_port = os.environ.get("DB_PORT", "5432")
    db_name = os.environ.get("DB_NAME") or os.environ.get("POSTGRES_DB")

    if db_user and db_password and db_name:
        return f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"

    return None


def test_with_sqlalchemy(uri):
    """Test database connection using SQLAlchemy."""
    print("\n--- Testing with SQLAlchemy ---")
    if not HAVE_SQLALCHEMY:
        print("SQLAlchemy is not installed. Install with: pip install sqlalchemy")
        return False

    try:
        print(f"Creating engine with URI: {mask_password(uri)}")
        engine = create_engine(uri)

        print("Connecting to database...")
        with engine.connect() as connection:
            print("Connection established successfully")

            print("Executing test query...")
            result = connection.execute(text("SELECT 1"))
            print(f"Query result: {result.scalar()}")

            print("Testing database metadata...")
            # Get list of tables
            result = connection.execute(
                text(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema = 'public'"
                )
            )
            tables = [row[0] for row in result]
            if tables:
                print(f"Found {len(tables)} tables: {', '.join(tables)}")
            else:
                print("No tables found in the database")

        return True
    except SQLAlchemyError as e:
        print(f"SQLAlchemy Error: {str(e)}")
        print(traceback.format_exc())
        return False
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        print(traceback.format_exc())
        return False


def test_with_psycopg2(uri):
    """Test database connection using psycopg2."""
    print("\n--- Testing with psycopg2 ---")
    if not HAVE_PSYCOPG2:
        print("psycopg2 is not installed. Install with: pip install psycopg2-binary")
        return False

    try:
        # Parse the URI to get connection parameters
        parsed = urlparse(uri)
        dbname = parsed.path[1:]  # Remove leading slash
        user = parsed.username
        password = parsed.password
        host = parsed.hostname
        port = parsed.port or 5432

        print(f"Connecting to PostgreSQL at {host}:{port}/{dbname} as {user}")
        conn = psycopg2.connect(
            dbname=dbname, user=user, password=password, host=host, port=port
        )

        print("Connection established successfully")

        # Create a cursor
        cur = conn.cursor()

        # Execute a test query
        print("Executing test query...")
        cur.execute("SELECT 1")
        result = cur.fetchone()
        print(f"Query result: {result[0]}")

        # Get list of tables
        print("Testing database metadata...")
        cur.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'public'"
        )
        tables = [row[0] for row in cur.fetchall()]
        if tables:
            print(f"Found {len(tables)} tables: {', '.join(tables)}")
        else:
            print("No tables found in the database")

        # Close cursor and connection
        cur.close()
        conn.close()
        print("Connection closed")

        return True
    except psycopg2.Error as e:
        print(f"psycopg2 Error: {str(e)}")
        print(traceback.format_exc())
        return False
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        print(traceback.format_exc())
        return False


def mask_password(uri):
    """Mask the password in the URI for display."""
    if not uri:
        return None

    try:
        parsed = urlparse(uri)
        if parsed.password:
            masked = uri.replace(parsed.password, "********")
            return masked
        return uri
    except Exception:
        # If parsing fails, just return a generic masked string
        return "database-uri-with-masked-password"


def main():
    """Main function to test database connection."""
    print("Database Connection Test")
    print("=======================")

    # Get database URI
    uri = get_database_uri()
    if not uri:
        print("Error: No database URI found in environment variables")
        print("Please set DATABASE_URL or SQLALCHEMY_DATABASE_URI")
        return 1

    print(f"Found database URI: {mask_password(uri)}")

    # Test with SQLAlchemy
    sqlalchemy_success = test_with_sqlalchemy(uri)

    # Test with psycopg2
    psycopg2_success = test_with_psycopg2(uri)

    # Print summary
    print("\n--- Summary ---")
    print(f"SQLAlchemy test: {'SUCCESS' if sqlalchemy_success else 'FAILED'}")
    print(f"psycopg2 test: {'SUCCESS' if psycopg2_success else 'FAILED'}")

    if sqlalchemy_success and psycopg2_success:
        print("\nAll database connection tests passed successfully!")
        return 0
    else:
        print("\nSome database connection tests failed. See above for details.")
        return 1


if __name__ == "__main__":
    sys.exit(main())

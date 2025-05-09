#!/usr/bin/env python3
# test_railway_db.py
import os
import sys
import psycopg2


def test_railway_db_connection():
    """Test connection to Railway PostgreSQL database"""
    print("Testing connection to Railway PostgreSQL database...")

    # Try to get connection parameters from environment
    db_url = os.environ.get('DATABASE_URL')

    if db_url:
        print(
            f"Using DATABASE_URL: {db_url.split('@')[0].split(':')[0]}:****@{db_url.split('@')[1] if '@' in db_url else '(no host info)'}")
        try:
            conn = psycopg2.connect(db_url)
            print("✅ Connection successful!")

            # Test a simple query
            with conn.cursor() as cur:
                cur.execute("SELECT version();")
                version = cur.fetchone()
                print(f"PostgreSQL version: {version[0]}")

            conn.close()
            return True
        except Exception as e:
            print(f"❌ Connection failed: {str(e)}")
            return False
    else:
        print("DATABASE_URL not found in environment")

        # Try individual PostgreSQL variables
        pghost = os.environ.get('PGHOST')
        pguser = os.environ.get('PGUSER')
        pgpassword = os.environ.get('PGPASSWORD')
        pgdatabase = os.environ.get('PGDATABASE')
        pgport = os.environ.get('PGPORT', '5432')

        if pghost and pguser and pgpassword and pgdatabase:
            print(
                f"Using PostgreSQL variables: {pguser}@{pghost}:{pgport}/{pgdatabase}")
            try:
                conn = psycopg2.connect(
                    host=pghost,
                    port=pgport,
                    user=pguser,
                    password=pgpassword,
                    database=pgdatabase
                )
                print("✅ Connection successful!")

                # Test a simple query
                with conn.cursor() as cur:
                    cur.execute("SELECT version();")
                    version = cur.fetchone()
                    print(f"PostgreSQL version: {version[0]}")

                conn.close()
                return True
            except Exception as e:
                print(f"❌ Connection failed: {str(e)}")
                return False
        else:
            print("❌ No database connection parameters found!")
            return False


if __name__ == "__main__":
    if test_railway_db_connection():
        sys.exit(0)
    else:
        sys.exit(1)

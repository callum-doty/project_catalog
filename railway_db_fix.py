#!/usr/bin/env python3
# railway_db_fix.py
import os
import sys
import psycopg2

# Railway PostgreSQL connection parameters (from your output)
RAILWAY_DB_PARAMS = {
    'host': 'shinkansen.proxy.rlwy.net',
    'port': '52940',
    'database': 'railway',
    'user': 'postgres',
    'password': 'ktUhwMMfeuiDxLHwSNLoEwGfPoenjCZI'
}


def test_direct_connection():
    """Test direct connection to Railway PostgreSQL"""
    print("\n=== TESTING DIRECT CONNECTION TO RAILWAY POSTGRESQL ===\n")

    try:
        print(
            f"Connecting to {RAILWAY_DB_PARAMS['host']}:{RAILWAY_DB_PARAMS['port']} as {RAILWAY_DB_PARAMS['user']}")
        conn = psycopg2.connect(
            host=RAILWAY_DB_PARAMS['host'],
            port=RAILWAY_DB_PARAMS['port'],
            dbname=RAILWAY_DB_PARAMS['database'],
            user=RAILWAY_DB_PARAMS['user'],
            password=RAILWAY_DB_PARAMS['password']
        )

        # Test a simple query
        cur = conn.cursor()
        cur.execute("SELECT version();")
        version = cur.fetchone()
        print(f"✅ Connection successful! PostgreSQL version: {version[0]}")

        # Check if the tables exist
        cur.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
            ORDER BY table_name;
        """)
        tables = cur.fetchall()
        print(f"\nFound {len(tables)} tables:")
        for table in tables:
            print(f"  - {table[0]}")

        cur.close()
        conn.close()
        return True

    except Exception as e:
        print(f"❌ Connection failed: {str(e)}")
        return False


def setup_environment_vars():
    """Set up environment variables for the application"""
    # Set the direct DATABASE_URL
    db = RAILWAY_DB_PARAMS
    os.environ['DATABASE_URL'] = f"postgresql://{db['user']}:{db['password']}@{db['host']}:{db['port']}/{db['database']}"
    os.environ['SQLALCHEMY_DATABASE_URI'] = os.environ['DATABASE_URL']

    # Set individual PostgreSQL variables
    os.environ['PGHOST'] = db['host']
    os.environ['PGPORT'] = db['port']
    os.environ['PGDATABASE'] = db['database']
    os.environ['PGUSER'] = db['user']
    os.environ['PGPASSWORD'] = db['password']

    print("Environment variables set:")
    print(
        f"DATABASE_URL=postgresql://{db['user']}:****@{db['host']}:{db['port']}/{db['database']}")
    print(f"PGHOST={db['host']}")
    print(f"PGPORT={db['port']}")
    print(f"PGDATABASE={db['database']}")
    print(f"PGUSER={db['user']}")
    print("PGPASSWORD=****")


if __name__ == "__main__":
    setup_environment_vars()
    if test_direct_connection():
        print("\n✅ Connection test passed! Your database is accessible.")
        sys.exit(0)
    else:
        print("\n❌ Connection test failed. Please check the connection details.")
        sys.exit(1)

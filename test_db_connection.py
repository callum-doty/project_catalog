import psycopg2

# Connection parameters
host = "shinkansen.proxy.rlwy.net"
port = "52940"
database = "railway"
user = "postgres"
password = "ktUhwMMfeuiDxLHwSNLoEwGfPoenJCZI"

try:
    # Connect to the database
    print("Connecting to PostgreSQL database...")
    conn = psycopg2.connect(
        host=host,
        port=port,
        database=database,
        user=user,
        password=password
    )

    # Create a cursor
    cur = conn.cursor()

    # Execute a test query
    print("Connected! Executing test query...")
    cur.execute("SELECT version();")

    # Fetch the result
    version = cur.fetchone()
    print(f"PostgreSQL version: {version[0]}")

    # Close cursor and connection
    cur.close()
    conn.close()
    print("Connection closed.")

except Exception as e:
    print(f"Error: {str(e)}")

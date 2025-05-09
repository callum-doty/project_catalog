#!/usr/bin/env python3
# railway_debug.py
import os
import sys


def debug_connection():
    """Print all environment variables related to database connections"""
    print("=== DATABASE CONNECTION DEBUGGING ===")

    # Check Railway-specific variables
    railway_vars = {k: v for k, v in os.environ.items()
                    if 'RAILWAY' in k.upper()}
    print("\nRAILWAY ENVIRONMENT VARIABLES:")
    for key, value in railway_vars.items():
        print(f"{key}={value}")

    # Check PostgreSQL variables
    pg_vars = {k: v for k, v in os.environ.items()
               if any(x in k.upper() for x in ['PG', 'POSTGRES', 'DATABASE', 'SQL'])}
    print("\nDATABASE ENVIRONMENT VARIABLES:")
    for key, value in pg_vars.items():
        if 'PASSWORD' in key.upper() or 'SECRET' in key.upper():
            print(f"{key}=********")
        else:
            print(f"{key}={value}")

    # Check constructed DATABASE_URL
    db_url = os.environ.get('DATABASE_URL', 'Not set')
    if 'PASSWORD' in db_url:
        # Mask password in the URL for security
        parts = db_url.split('@')
        if len(parts) > 1:
            auth_parts = parts[0].split(':')
            if len(auth_parts) > 2:
                masked_url = f"{auth_parts[0]}:{auth_parts[1]}:********@{parts[1]}"
                print(f"\nDATABASE_URL={masked_url}")
            else:
                print(
                    f"\nDATABASE_URL={parts[0].split(':')[0]}:********@{parts[1]}")
        else:
            print(f"\nDATABASE_URL={db_url}")
    else:
        print(f"\nDATABASE_URL={db_url}")

    print("\n=== END DEBUG INFO ===")


if __name__ == "__main__":
    debug_connection()

#!/usr/bin/env python3
# railway_debug.py
import os


def debug_connection():
    """Print all environment variables related to database connections"""
    print("=== DATABASE CONNECTION DEBUGGING ===")

    # Print all environment variables (masking sensitive ones)
    print("\nALL ENVIRONMENT VARIABLES:")
    for key, value in sorted(os.environ.items()):
        if any(x in key.upper() for x in ['PASSWORD', 'SECRET', 'KEY']):
            print(f"{key}=********")
        else:
            print(f"{key}={value}")

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

    print("\n=== END DEBUG INFO ===")


if __name__ == "__main__":
    debug_connection()

#!/usr/bin/env python
"""
Script to fix the SQLAlchemy text() issue in the health check endpoint.
This updates the health check in src/catalog/__init__.py to use explicit text declaration.
"""

import os
import re


def fix_health_check():
    """Fix the health check in __init__.py to use explicit text declaration."""
    init_file = "src/catalog/__init__.py"

    if not os.path.exists(init_file):
        print(f"Error: {init_file} not found")
        return False

    with open(init_file, "r") as f:
        content = f.read()

    # Check if we need to add the import
    if "from sqlalchemy import text" not in content:
        # Add import
        content = re.sub(
            r"from flask_sqlalchemy import SQLAlchemy",
            "from flask_sqlalchemy import SQLAlchemy\nfrom sqlalchemy import text",
            content,
        )

    # Fix the health check query
    content = re.sub(
        r'db\.session\.execute\("SELECT 1"\)',
        'db.session.execute(text("SELECT 1"))',
        content,
    )

    # Also fix in wsgi.py if it exists
    wsgi_file = "src/wsgi.py"
    if os.path.exists(wsgi_file):
        with open(wsgi_file, "r") as f:
            wsgi_content = f.read()

        if 'db.session.execute("SELECT 1")' in wsgi_content:
            # Add import if needed
            if "from sqlalchemy import text" not in wsgi_content:
                wsgi_content = re.sub(
                    r"import os", "import os\nfrom sqlalchemy import text", wsgi_content
                )

            # Fix the query
            wsgi_content = re.sub(
                r'db\.session\.execute\("SELECT 1"\)',
                'db.session.execute(text("SELECT 1"))',
                wsgi_content,
            )

            with open(wsgi_file, "w") as f:
                f.write(wsgi_content)
            print(f"Updated {wsgi_file}")

    # Fix in main_routes.py health check if it exists
    main_routes_file = "src/catalog/web/main_routes.py"
    if os.path.exists(main_routes_file):
        with open(main_routes_file, "r") as f:
            routes_content = f.read()

        if 'db.session.execute("SELECT 1")' in routes_content:
            # Add import if needed
            if "from sqlalchemy import text" not in routes_content:
                routes_content = re.sub(
                    r"from flask import",
                    "from sqlalchemy import text\nfrom flask import",
                    routes_content,
                )

            # Fix the query
            routes_content = re.sub(
                r'db\.session\.execute\("SELECT 1"\)',
                'db.session.execute(text("SELECT 1"))',
                routes_content,
            )

            with open(main_routes_file, "w") as f:
                f.write(routes_content)
            print(f"Updated {main_routes_file}")

    # Write the updated content back to the file
    with open(init_file, "w") as f:
        f.write(content)

    print(f"Updated {init_file}")
    return True


if __name__ == "__main__":
    if fix_health_check():
        print("Successfully fixed SQLAlchemy text() issue in health check endpoints")
        print("Please restart your application for changes to take effect")
    else:
        print("Failed to fix health check endpoints")

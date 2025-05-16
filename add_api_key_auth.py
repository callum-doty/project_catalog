#!/usr/bin/env python
"""
Script to add API key authentication to the application.
This allows API routes to be accessed without session-based authentication
by providing an API key in the request header or query parameter.
"""

import os
import re
import secrets
import sys


def generate_api_key():
    """Generate a secure API key."""
    return secrets.token_urlsafe(32)


def add_api_key_auth():
    """Add API key authentication to the application."""
    main_routes_file = "src/catalog/web/main_routes.py"

    if not os.path.exists(main_routes_file):
        print(f"Error: {main_routes_file} not found")
        return False

    # Generate a secure API key
    api_key = generate_api_key()

    with open(main_routes_file, "r") as f:
        content = f.read()

    # Check if API key auth is already implemented
    if "def check_api_key" in content:
        print("API key authentication already implemented")
        return True

    # Add API key check function
    protect_blueprint_pattern = (
        r"@main_routes\.before_request\s+def protect_blueprint\(\):"
    )
    api_key_function = """
# API key for programmatic access
API_KEY = os.environ.get("API_KEY", "{api_key}")

def check_api_key(request):
    \"\"\"Check if the request has a valid API key.\"\"\"
    # Check header first (preferred method)
    api_key_header = request.headers.get("X-API-Key")
    if api_key_header and api_key_header == API_KEY:
        return True
    
    # Check query parameter as fallback
    api_key_param = request.args.get("api_key")
    if api_key_param and api_key_param == API_KEY:
        return True
    
    return False

""".format(
        api_key=api_key
    )

    # Insert API key function before protect_blueprint
    content = re.sub(
        protect_blueprint_pattern,
        api_key_function + "\n" + protect_blueprint_pattern,
        content,
    )

    # Modify protect_blueprint to check for API key
    protect_blueprint_body_pattern = r"(@main_routes\.before_request\s+def protect_blueprint\(\):.*?# Check if authenticated\s+if not session\.get\(\"authenticated\"\):)"

    # Add API key check
    modified_protect_blueprint = r"\1\n    # Check for API key for API routes\n    if request.path.startswith('/api/') and check_api_key(request):\n        return None\n"

    content = re.sub(
        protect_blueprint_body_pattern,
        modified_protect_blueprint,
        content,
        flags=re.DOTALL,
    )

    # Write the updated content back to the file
    with open(main_routes_file, "w") as f:
        f.write(content)

    print(f"Updated {main_routes_file}")
    print(f"\nGenerated API key: {api_key}")
    print("\nTo use this API key:")
    print("1. Set it as an environment variable in Render:")
    print(f"   API_KEY={api_key}")
    print("\n2. Include it in your API requests:")
    print("   - As a header: X-API-Key: {your_api_key}")
    print("   - Or as a query parameter: ?api_key={your_api_key}")
    print("\nExample:")
    print(
        f'   curl -H "X-API-Key: {api_key}" https://catalog-web-jx5m.onrender.com/api/search'
    )
    print(
        f'   curl "https://catalog-web-jx5m.onrender.com/api/search?api_key={api_key}"'
    )

    return True


if __name__ == "__main__":
    if add_api_key_auth():
        print("\nSuccessfully added API key authentication")
        print("Please restart your application for changes to take effect")
    else:
        print("Failed to add API key authentication")
        sys.exit(1)

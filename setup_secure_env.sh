#!/bin/bash

# setup_secure_env.sh
# Helper script to set up secure environment variables for Document Catalog

echo "Setting up secure environment for Document Catalog"
echo "=================================================="

# Detect if we're running in a production environment
read -p "Are you running this in production with HTTPS? (y/n): " production_env
if [[ $production_env == "y" || $production_env == "Y" ]]; then
    export SECURE_COOKIES=true
    export BEHIND_PROXY=true
    echo "✅ Production environment detected. Using secure settings."
else
    export SECURE_COOKIES=false
    export BEHIND_PROXY=false
    echo "ℹ️ Development environment detected. Using standard settings."
fi

# Generate a secure random key if one doesn't exist
if [[ -z "$SECRET_KEY" ]]; then
    # Generate a random 32-character string
    RANDOM_KEY=$(openssl rand -hex 16)
    export SECRET_KEY=$RANDOM_KEY
    echo "✅ Generated new SECRET_KEY"
fi

# Set site password if not already set
if [[ -z "$SITE_PASSWORD" ]]; then
    read -p "Enter a secure site password (or press enter to use the default): " password
    if [[ -z "$password" ]]; then
        password="your_secure_password"
        echo "⚠️ Using default password - change this in production!"
    else
        echo "✅ Custom password set"
    fi
    export SITE_PASSWORD=$password
fi

echo ""
echo "Environment variables set successfully!"
echo ""
echo "To make these settings permanent, add the following to your .env file:"
echo "SECRET_KEY=$SECRET_KEY"
echo "SITE_PASSWORD=$SITE_PASSWORD"
echo "SECURE_COOKIES=$SECURE_COOKIES"
echo "BEHIND_PROXY=$BEHIND_PROXY"
echo ""
echo "Now restart your application for the changes to take effect."

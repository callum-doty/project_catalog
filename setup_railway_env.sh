#!/bin/bash

# setup_railway_env.sh
# Script to set up Railway.app specific environment variables

echo "Setting up environment variables for Railway.app deployment"
echo "=========================================================="

# Check if we're running in Railway's environment
if [ -n "$RAILWAY_ENVIRONMENT" ]; then
    echo "✅ Detected Railway.app environment"
    
    # Force secure settings for Railway 
    echo "Setting secure configuration for Railway.app..."
    
    # These settings will be applied through Railway's environment variables
    cat << EOF

To eliminate the "information you're about to submit is not secure" warning,
add these environment variables in your Railway.app project settings:

SECURE_COOKIES=true
BEHIND_PROXY=true
PREFERRED_URL_SCHEME=https

EOF
else
    echo "⚠️ This script is intended to be run in a Railway.app environment."
    echo "You can still manually set these variables in your Railway.app project settings."
fi

# Instructions for Railway.app
echo ""
echo "IMPORTANT: To configure these variables in Railway.app:"
echo "1. Go to your Railway.app project dashboard"
echo "2. Click on your service (e.g., 'document-catalog')"
echo "3. Go to the 'Variables' tab"
echo "4. Add each of the environment variables listed above"
echo "5. Deploy your application again to apply these changes"
echo ""
echo "These settings will ensure your application handles HTTPS properly in Railway.app's environment." 
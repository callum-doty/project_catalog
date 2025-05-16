# Comprehensive Render Deployment Guide

This guide provides step-by-step instructions for fully deploying your Document Catalog application on Render, including fixing common issues and setting up API access.

## Current Deployment Status

Your application is successfully deployed on Render at https://catalog-web-jx5m.onrender.com/ and is returning the basic API response:

```json
{
  "message": "Document Catalog API is running",
  "status": "online",
  "version": "1.0.0"
}
```

However, there are a few issues to address:

1. The health check endpoint has a SQLAlchemy error
2. API routes require authentication
3. Database migrations may need to be applied

## Step 1: SSH into Your Render Instance

1. Log in to your Render dashboard
2. Navigate to your web service (catalog-web-jx5m)
3. Click on the "Shell" tab to access SSH

## Step 2: Fix the SQLAlchemy Text() Issue

The health check endpoint is showing an error because of a SQLAlchemy version compatibility issue. Run the provided script to fix it:

```bash
# Make the script executable
chmod +x fix_health_check.py

# Run the script
python fix_health_check.py

# Restart the application (Render will do this automatically when you exit the shell)
```

## Step 3: Apply Database Migrations

Ensure your database schema is up to date:

```bash
# Set the Flask app
export FLASK_APP=src/wsgi.py

# Run migrations
python -m flask db upgrade

# Initialize taxonomy if needed
python scripts/initialize_taxonomy.py
```

## Step 4: Set Environment Variables

In the Render dashboard, add these environment variables:

1. `SITE_PASSWORD`: Set a secure password for web access
2. `API_KEY`: (Optional) Set an API key for programmatic access without authentication

## Step 5: Enable API Key Authentication (Optional)

If you want to access the API routes programmatically without session-based authentication:

```bash
# Make the script executable
chmod +x add_api_key_auth.py

# Run the script
python add_api_key_auth.py

# Note the generated API key and set it as an environment variable in Render
```

## Step 6: Restart Your Application

Exit the SSH shell to trigger a restart of your application:

```bash
exit
```

## Step 7: Verify Deployment

### Test the Health Check

```bash
curl https://catalog-web-jx5m.onrender.com/health
```

Expected response:

```json
{ "status": "healthy", "database": "connected" }
```

### Test the Search API with Authentication

#### Web Access:

1. Visit https://catalog-web-jx5m.onrender.com/api/password-check
2. Enter your SITE_PASSWORD
3. You'll be redirected to the search page

#### API Access with API Key:

```bash
# Using header authentication
curl -H "X-API-Key: YOUR_API_KEY" https://catalog-web-jx5m.onrender.com/api/search

# Using query parameter
curl "https://catalog-web-jx5m.onrender.com/api/search?api_key=YOUR_API_KEY"
```

## Troubleshooting

### Database Connection Issues

If you encounter database connection issues:

```bash
# Check database connection string
env | grep DATABASE_URL

# Test database connection
python -c "import psycopg2; conn = psycopg2.connect('$DATABASE_URL'); print('Connection successful')"
```

### Application Not Starting

Check the logs in the Render dashboard for error messages. Common issues include:

1. Missing environment variables
2. Database migration errors
3. Port binding issues

### Authentication Issues

If authentication is not working:

1. Verify the SITE_PASSWORD environment variable is set
2. Check for any errors in the application logs
3. Try clearing your browser cookies and cache

## Monitoring and Maintenance

### View Logs

In the Render dashboard, click on the "Logs" tab to view application logs.

### Update Environment Variables

In the Render dashboard, click on the "Environment" tab to update environment variables.

### Restart the Application

In the Render dashboard, click on the "Manual Deploy" button and select "Clear build cache & deploy".

## Next Steps

1. Set up continuous integration/deployment (CI/CD) with your Git repository
2. Configure automatic database backups
3. Set up monitoring and alerting
4. Implement rate limiting for API endpoints

## Additional Resources

- [Render Documentation](https://render.com/docs)
- [Flask Documentation](https://flask.palletsprojects.com/)
- [SQLAlchemy Documentation](https://docs.sqlalchemy.org/)

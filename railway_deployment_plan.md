# Railway Deployment Plan

## Services to Configure

1. **Web Application**

   - Source: Deploy from GitHub
   - Service Name: web
   - Environment Variables:

     ```
     FLASK_APP=wsgi.py
     FLASK_ENV=production
     SECRET_KEY=generate-a-secure-random-key
     CLAUDE_API_KEY=your-claude-api-key
     DROPBOX_ACCESS_TOKEN=your-dropbox-token
     DROPBOX_FOLDER_PATH=/your-folder-path

     # Use S3 for storage
     STORAGE_TYPE=s3
     S3_ACCESS_KEY=from-railway-s3-plugin
     S3_SECRET_KEY=from-railway-s3-plugin
     S3_ENDPOINT_URL=from-railway-s3-plugin
     S3_REGION=us-east-1
     STORAGE_BUCKET=documents
     ```

2. **PostgreSQL Database**

   - Add a PostgreSQL service from Railway
   - Environment Variables for Web App:
     ```
     DATABASE_URL=${POSTGRESQL_URL}
     SQLALCHEMY_DATABASE_URI=${POSTGRESQL_URL}
     ```

3. **Redis**

   - Add a Redis service from Railway
   - Environment Variables for Web App:
     ```
     CELERY_BROKER_URL=redis://${REDIS_HOST}:${REDIS_PORT}/0
     CELERY_RESULT_BACKEND=redis://${REDIS_HOST}:${REDIS_PORT}/0
     ```

4. **Celery Worker**

   - Source: Same as Web App
   - Service Name: celery-worker
   - Start Command: `celery -A tasks worker -Q document_processing,analysis --loglevel=info`
   - Environment Variables: Same as Web App

5. **Celery Beat**
   - Source: Same as Web App
   - Service Name: celery-beat
   - Start Command: `celery -A tasks beat --loglevel=info`
   - Environment Variables: Same as Web App

## Steps to Deploy

1. **Create New Project on Railway**

   - Go to your Railway dashboard and create a new project

2. **Add PostgreSQL and Redis Services**

   - Add the database services first
   - Note the connection details provided

3. **Deploy Web App**

   - Deploy from your GitHub repository
   - Configure all environment variables
   - Set the start command: `gunicorn --bind 0.0.0.0:$PORT wsgi:application`

4. **Deploy Celery Services**

   - Add two more services using the same repository
   - Configure them as celery-worker and celery-beat
   - Set the respective start commands
   - Use the same environment variables as the web app

5. **Initialize Database**

   - Use Railway's terminal to run:
     ```
     flask db upgrade
     ```

6. **Monitor Deployment**

   - Check the logs for any errors
   - Verify that all services are connecting properly

7. **Access Your Application**
   - Use the domain provided by Railway
   - Test all functionality with a small sample file

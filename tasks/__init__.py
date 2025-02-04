# tasks/__init__.py

from celery import Celery
from config.settings import settings

def create_celery_app(app=None):
    celery = Celery('tasks')
    
    # Configure Celery using the settings attributes
    celery.conf.update(
        broker_url=settings.broker_url,
        result_backend=settings.result_backend,
        task_serializer=settings.task_serializer,
        result_serializer=settings.result_serializer,
        accept_content=settings.accept_content,
        timezone=settings.timezone,
        enable_utc=settings.enable_utc,
        task_routes=settings.task_routes,
        imports=['tasks.document_tasks']
    )
    
    class ContextTask(celery.Task):
        def __call__(self, *args, **kwargs):
            if app:
                with app.app_context():
                    return self.run(*args, **kwargs)
            return self.run(*args, **kwargs)
    
    celery.Task = ContextTask
    return celery

# Create the Celery app
celery_app = create_celery_app()
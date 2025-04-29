# tasks/task_base.py
import sys
import logging

# Add the parent directory to the Python path
sys.path.insert(0, '/app')

logger = logging.getLogger(__name__)

try:
    import celery
    from celery import Task
    logger.info("Successfully imported Task from celery")
except ImportError as e:
    logger.error(f"Failed to import Task from celery: {str(e)}")
    raise


class DocumentProcessor(Task):
    abstract = True
    _storage = None
    _llm_service = None

    @property
    def storage(self):
        if self._storage is None:
            from catalog.services.storage_service import MinIOStorage
            self._storage = MinIOStorage()
        return self._storage

    @property
    def llm_service(self):
        if self._llm_service is None:
            from catalog.services.llm_service import LLMService
            self._llm_service = LLMService()
        return self._llm_service

    def download_temp_file(self, filename):
        """Download file to temp location for processing"""
        try:
            temp_path = f"/tmp/{filename}"
            self.storage.download_file(filename, temp_path)
            return temp_path
        except Exception as e:
            logger.error(f"Error downloading file: {str(e)}")
            return None

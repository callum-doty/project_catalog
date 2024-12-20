# src/integrations/dropbox_handler.py
from dropbox import Dropbox
from dropbox.files import FileMetadata, ListFolderResult
from dropbox.exceptions import ApiError
import logging
import os

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


class DropboxHandler:
    def __init__(self):
        self.app_key = os.getenv('DROPBOX_APP_KEY')
        self.app_secret = os.getenv('DROPBOX_APP_SECRET')
        self.refresh_token = os.getenv('DROPBOX_REFRESH_TOKEN')

        # Initialize with refresh token
        self.dbx = Dropbox(
            oauth2_refresh_token=self.refresh_token,
            app_key=self.app_key,
            app_secret=self.app_secret
        )

    def test_connection(self):
        """Test the Dropbox connection and permissions"""
        try:
            account = self.dbx.users_get_current_account()
            logger.info(
                f"Successfully connected to Dropbox account: {account.email}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to Dropbox: {str(e)}")
            return False

    def list_documents(self, folder_path: str = "") -> ListFolderResult:
        """List all documents in a Dropbox folder"""
        try:
            logger.info(f"Attempting to list files in: {folder_path}")
            result = self.dbx.files_list_folder(folder_path)

            # Log what we found
            files = [entry for entry in result.entries if isinstance(
                entry, FileMetadata)]
            logger.info(f"Found {len(files)} files in {folder_path}")
            for file in files:
                logger.debug(
                    f"Found file: {file.name}, size: {file.size}, modified: {file.server_modified}")

            return files
        except ApiError as e:
            logger.error(f"Dropbox API error: {str(e)}")
            if e.error.is_path():
                logger.error(
                    f"Path error - folder might not exist: {folder_path}")
            raise
        except Exception as e:
            logger.error(f"Error listing Dropbox files: {str(e)}")
            raise

# src/integrations/dropbox_handler.py
from dropbox import Dropbox
from dropbox.files import FileMetadata, ListFolderResult
from dropbox.exceptions import ApiError, AuthError
import logging
import os

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


class DropboxHandler:
    def __init__(self):
        logger.debug("Initializing DropboxHandler")
        self.app_key = os.getenv('DROPBOX_APP_KEY')
        self.app_secret = os.getenv('DROPBOX_APP_SECRET')
        self.refresh_token = os.getenv('DROPBOX_REFRESH_TOKEN')

        logger.debug(f"App Key present: {'yes' if self.app_key else 'no'}")
        logger.debug(
            f"App Secret present: {'yes' if self.app_secret else 'no'}")
        logger.debug(
            f"Refresh Token present: {'yes' if self.refresh_token else 'no'}")

        try:
            self.dbx = Dropbox(
                oauth2_refresh_token=self.refresh_token,
                app_key=self.app_key,
                app_secret=self.app_secret
            )
            logger.debug("Dropbox client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Dropbox client: {str(e)}")
            raise

    def test_connection(self):
        """Test the Dropbox connection and permissions"""
        try:
            logger.debug("Testing Dropbox connection...")
            account = self.dbx.users_get_current_account()
            logger.info(
                f"Successfully connected to Dropbox account: {account.email}")
            return True
        except AuthError as e:
            logger.error(f"Authentication error: {str(e)}")
            return False
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
        except AuthError as e:
            logger.error(f"Authentication error while listing files: {str(e)}")
            raise
        except ApiError as e:
            logger.error(f"Dropbox API error: {str(e)}")
            if e.error.is_path():
                logger.error(
                    f"Path error - folder might not exist: {folder_path}")
            raise
        except Exception as e:
            logger.error(f"Error listing Dropbox files: {str(e)}")
            raise

    def download_file(self, file_path: str):
        """Download a file from Dropbox"""
        try:
            logger.debug(f"Downloading file: {file_path}")
            metadata, response = self.dbx.files_download(file_path)
            logger.debug(f"Successfully downloaded {metadata.name}")
            return response.content
        except Exception as e:
            logger.error(f"Error downloading file {file_path}: {str(e)}")
            raise

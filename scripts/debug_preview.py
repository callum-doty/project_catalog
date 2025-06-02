import os
import sys
import argparse
from dotenv import load_dotenv

# Add project root to sys.path to allow imports from src
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Conditional imports to catch issues early if environment is not set up
try:
    from src.catalog import create_app, db
    from src.catalog.models.document import Document
    from src.catalog.services.storage_service import (
        MinIOStorage,
    )  # Changed StorageService to MinIOStorage
except ImportError as e:
    print(f"Error: Could not import necessary modules: {e}")
    print("Please ensure that the script is run from the project root directory and")
    print("that the virtual environment is activated, or PYTHONPATH is set correctly.")
    sys.exit(1)


def debug_document_preview(document_id_to_debug):
    """
    Checks the status of a document's preview and provides debugging information.
    """
    env_path = os.path.join(project_root, ".env")
    if os.path.exists(env_path):
        load_dotenv(env_path)
        print(f"INFO: Loaded environment variables from {env_path}")
    else:
        print(
            f"WARNING: .env file not found at {env_path}. Script may not have all necessary configurations."
        )

    app = create_app()

    with app.app_context():
        print(f"\n--- Debugging Preview for Document ID: {document_id_to_debug} ---")

        doc = db.session.get(Document, document_id_to_debug)

        if not doc:
            print(f"ERROR: Document with ID {document_id_to_debug} not found.")
            print("--- End of Debugging ---")
            return

        print("\n[1] Document Information:")
        print(f"  - ID: {doc.id}")
        print(f"  - Filename: {getattr(doc, 'filename', 'N/A')}")
        print(f"  - Uploaded At: {getattr(doc, 'uploaded_at', 'N/A')}")

        preview_status = getattr(doc, "preview_status", "N/A (field not found)")
        s3_preview_key = getattr(doc, "s3_preview_key", None)
        preview_task_id = getattr(doc, "preview_task_id", "N/A (field not found)")
        # Check for common error message attribute names
        preview_error = getattr(
            doc,
            "preview_error_message",
            getattr(doc, "error_message", "N/A (field not found)"),
        )
        preview_generated_at = getattr(
            doc, "preview_generated_at", "N/A (field not found)"
        )

        print(f"  - Preview Status: {preview_status}")
        print(f"  - Preview S3 Key: {s3_preview_key if s3_preview_key else 'Not set'}")
        print(f"  - Preview Task ID: {preview_task_id}")
        print(f"  - Preview Error Message: {preview_error}")
        print(f"  - Preview Generated At: {preview_generated_at}")

        if preview_status == "FAILED" or (
            isinstance(preview_status, str) and "FAIL" in preview_status.upper()
        ):
            print(
                "\n  WARNING: Preview generation seems to have failed for this document."
            )
            print(f"    Error message recorded: {preview_error}")
            print(
                f"    Consider checking Celery worker logs for task ID: {preview_task_id}"
            )

        if preview_status == "PENDING" or (
            isinstance(preview_status, str) and "PEND" in preview_status.upper()
        ):
            print(
                "\n  INFO: Preview generation appears to be pending for this document."
            )
            print(f"    Celery task ID: {preview_task_id}")
            print(
                f"    Check if Celery workers are running and processing tasks from the correct queue."
            )
            print(
                f"    Check Celery worker logs for this task ID for progress or errors."
            )

        print("\n[2] Storage Check (S3/Minio):")
        if not s3_preview_key:
            print("  - No S3 preview key found for this document in the database.")
            print(
                "    Preview might not have been attempted, failed very early, or the key was not stored."
            )
        else:
            try:
                storage_service = (
                    MinIOStorage()  # Changed StorageService to MinIOStorage
                )  # Assumes it can be instantiated and configured

                # Determine bucket name (common config keys)
                preview_bucket = app.config.get(
                    "S3_PREVIEW_BUCKET", app.config.get("S3_BUCKET_NAME")
                )

                if not preview_bucket:
                    print(
                        "  - ERROR: S3_PREVIEW_BUCKET or S3_BUCKET_NAME not configured in the Flask app."
                    )
                    print(
                        "    Cannot check for object existence without a bucket name."
                    )
                else:
                    print(
                        f"  - Attempting to check for object '{s3_preview_key}' in bucket '{preview_bucket}'..."
                    )
                    # Assumption: StorageService has an 'object_exists' method.
                    # If not, this part needs to be adapted to how StorageService checks for existence
                    # (e.g., trying to get metadata and catching specific exceptions).
                    if hasattr(storage_service, "object_exists"):
                        exists = storage_service.object_exists(
                            bucket_name=preview_bucket, object_name=s3_preview_key
                        )
                        if exists:
                            print(
                                f"  - SUCCESS: Preview file '{s3_preview_key}' reported to EXIST in bucket '{preview_bucket}'."
                            )
                            if hasattr(storage_service, "get_presigned_url"):
                                try:
                                    preview_url = storage_service.get_presigned_url(
                                        bucket_name=preview_bucket,
                                        object_name=s3_preview_key,
                                    )
                                    print(f"  - Potential Preview URL: {preview_url}")
                                except Exception as url_e:
                                    print(
                                        f"  - INFO: Could not generate presigned URL: {url_e}"
                                    )
                            else:
                                print(
                                    "  - INFO: StorageService does not have 'get_presigned_url' method."
                                )
                        else:
                            print(
                                f"  - ERROR: Preview file '{s3_preview_key}' reported as NOT FOUND in bucket '{preview_bucket}'."
                            )
                            if preview_status == "SUCCESS" or (
                                isinstance(preview_status, str)
                                and "SUCC" in preview_status.upper()
                            ):
                                print(
                                    "    WARNING: Document status is SUCCESS, but preview file is missing. This indicates an inconsistency!"
                                )
                    elif hasattr(storage_service, "s3_client") and hasattr(
                        storage_service.s3_client, "head_object"
                    ):
                        print(
                            "  - INFO: StorageService does not have 'object_exists'. Trying 'head_object' via s3_client."
                        )
                        try:
                            storage_service.s3_client.head_object(
                                Bucket=preview_bucket, Key=s3_preview_key
                            )
                            print(
                                f"  - SUCCESS: Preview file '{s3_preview_key}' EXISTS in bucket '{preview_bucket}' (confirmed via head_object)."
                            )
                            # Presigned URL attempt again if head_object worked
                            if hasattr(storage_service, "get_presigned_url"):
                                try:
                                    preview_url = storage_service.get_presigned_url(
                                        bucket_name=preview_bucket,
                                        object_name=s3_preview_key,
                                    )
                                    print(f"  - Potential Preview URL: {preview_url}")
                                except Exception as url_e:
                                    print(
                                        f"  - INFO: Could not generate presigned URL: {url_e}"
                                    )
                        except (
                            Exception
                        ) as head_e:  # Catching generic Exception, but boto3 often raises ClientError
                            if "404" in str(head_e) or "Not Found" in str(head_e):
                                print(
                                    f"  - ERROR: Preview file '{s3_preview_key}' NOT FOUND in bucket '{preview_bucket}' (via head_object: {head_e})."
                                )
                                if preview_status == "SUCCESS" or (
                                    isinstance(preview_status, str)
                                    and "SUCC" in preview_status.upper()
                                ):
                                    print(
                                        "    WARNING: Document status is SUCCESS, but preview file is missing. This indicates an inconsistency!"
                                    )
                            else:
                                print(
                                    f"  - ERROR: Error checking file with head_object: {head_e}"
                                )
                    else:
                        print(
                            "  - INFO: Could not check S3 object existence automatically."
                        )
                        print(
                            "    StorageService does not have a recognized 'object_exists' or 's3_client.head_object' method."
                        )
                        print(
                            f"    Please manually check your S3/Minio storage for the key '{s3_preview_key}' in bucket '{preview_bucket}'."
                        )

            except AttributeError as e:
                print(
                    f"  - INFO: Could not perform full S3 check due to missing attribute: {e}"
                )
                print(
                    "    This might indicate an issue with StorageService initialization or expected methods."
                )
            except Exception as e:
                print(
                    f"  - ERROR: An unexpected error occurred while checking S3 object: {e}"
                )

        print("\n[3] Frontend/Browser Debugging Steps:")
        print("  1. Open your browser's Developer Tools (usually by pressing F12).")
        print("  2. Go to the 'Network' tab. Keep it open.")
        print(
            "  3. Navigate to the page in your application where the document preview should load. Refresh if necessary."
        )
        print("  4. In the 'Network' tab, look for requests related to the preview:")
        print(
            "     - Is there a request to a URL similar to the S3 key or the 'Potential Preview URL' above?"
        )
        print(
            "     - What is the HTTP status code of this request (e.g., 200 OK, 403 Forbidden, 404 Not Found)?"
        )
        print("     - Check the response content if available.")
        print("  5. Go to the 'Console' tab in Developer Tools.")
        print(
            "     - Are there any JavaScript errors reported? These might prevent the preview from loading or displaying."
        )
        print(
            f"  6. If the preview is loaded by JavaScript (e.g., using '{s3_preview_key}'), verify that the URL being constructed and requested by the frontend code is correct and accessible from the browser."
        )

        print("\n[4] Application & Worker Log Check (Render Specific):")
        print(
            "  - Access your application and Celery worker logs via the Render Dashboard."
        )
        print(
            "  - For the Flask application (web service): Review logs for errors around the time of document upload or when a preview was requested."
        )
        print(
            f"  - For Celery workers: Filter logs for messages related to 'preview_tasks' or the specific Celery task ID '{preview_task_id}'."
        )
        print(
            "    Look for tracebacks, error messages, or reasons why the task might have failed, not started, or not completed."
        )
        print(
            "  - Ensure your Render environment variables (DATABASE_URL, S3/Minio credentials, S3_BUCKET_NAME, S3_PREVIEW_BUCKET etc.) are correctly set for all relevant services (web, worker)."
        )

        print("\n--- End of Debugging ---")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Debug document preview generation for the Catalog application.",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "document_id", type=int, help="The ID of the document to debug."
    )
    args = parser.parse_args()

    try:
        debug_document_preview(args.document_id)
    except NameError as e:
        if (
            "create_app" in str(e) or "Document" in str(e) or "MinIOStorage" in str(e)
        ):  # Changed StorageService to MinIOStorage
            # This case is already handled by the try-except block around imports,
            # but as a fallback if the script somehow proceeds.
            print(f"Fatal Error: A required component is not defined: {e}")
            print("This usually means the imports at the top of the script failed.")
        else:
            raise
    except Exception as e:
        print(f"An unexpected error occurred during script execution: {e}")
        import traceback

        traceback.print_exc()

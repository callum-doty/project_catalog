# src/catalog/services/llm_service.py
import os
import json
import httpx
import time
import base64
from typing import Dict, Any, List, Optional
from src.catalog.services.prompt_manager import PromptManager
import logging
import traceback
from src.catalog.constants import MODEL_SETTINGS, ERROR_MESSAGES

logger = logging.getLogger(__name__)


class LLMService:
    def __init__(self):
        self.api_key = os.getenv("CLAUDE_API_KEY")
        if not self.api_key:
            logger.error("CLAUDE_API_KEY environment variable is not set!")
            raise ValueError(ERROR_MESSAGES['AUTHENTICATION_FAILED'])

        self.headers = {
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
            "x-api-key": self.api_key
        }

        # Default to the Claude 3 Opus model
        self.model = os.getenv(
            "CLAUDE_MODEL", MODEL_SETTINGS['CLAUDE']['MODEL'])
        logger.info(f"Using Claude model: {self.model}")

        # Initialize prompt manager
        self.prompt_manager = PromptManager()

    def _get_file_data(self, filename: str) -> dict:
        """Get file data and path from storage if available"""
        try:
            from src.catalog.services.storage_service import MinIOStorage
            storage = MinIOStorage()

            # Check if file exists in storage
            logger.info(f"Retrieving file from MinIO: {filename}")
            temp_path = f"/tmp/{filename}"

            # Get file from MinIO and save to temp path
            try:
                file_data = storage.get_file(filename)
                if file_data:
                    with open(temp_path, "wb") as f:
                        f.write(file_data)
                    logger.info(f"File retrieved and saved to {temp_path}")
                    return {"path": temp_path, "exists": True}
            except Exception as e:
                logger.error(f"Failed to retrieve file from MinIO: {str(e)}")

            return {"path": None, "exists": False}
        except Exception as e:
            logger.error(f"Error getting file data: {str(e)}")
            return {"path": None, "exists": False}

    def analyze_document_modular(self, filename: str, document_path: Optional[str] = None, components: List[str] = None) -> Dict[Any, Any]:
        """
        Synchronous modular analysis with separate API calls for each component

        Args:
            filename: Document filename
            document_path: Path to document file (optional)
            components: List of analysis components to run (default: all)

        Returns:
            Combined analysis results
        """
        logger.info(
            f"Starting modular analysis for {filename} with components: {components}")

        # If document path not provided, try to fetch from storage
        if not document_path:
            file_info = self._get_file_data(filename)
            if file_info and file_info.get("exists"):
                document_path = file_info.get("path")
                logger.info(
                    f"Using document path from storage: {document_path}")

        # Default to all components if not specified
        if not components:
            components = [
                "metadata", "classification", "entities", "text",
                "design", "keywords", "communication"
            ]

        # Prepare image data once for all components
        image_data = self._prepare_image_data(document_path)
        if not image_data:
            logger.warning(f"Could not prepare image data for {filename}")

        # Initialize combined results
        results = {}
        metadata = None

        # Process components sequentially, collecting results
        for component in components:
            try:
                # Get the appropriate prompt for this component
                prompt = self._get_component_prompt(
                    component, filename, metadata)
                if not prompt:
                    logger.warning(
                        f"No prompt available for component: {component}")
                    continue

                # Call Claude API for this component
                logger.info(f"Processing component: {component}")
                component_result = self._call_claude_api_sync(
                    prompt, image_data, max_retries=3)

                # Store result for this component
                if component_result:
                    # For metadata component, extract and save for context in other components
                    if component == "metadata" and "document_analysis" in component_result:
                        metadata = component_result["document_analysis"]

                    # Add to combined results
                    results.update(component_result)
                    logger.info(
                        f"Successfully processed component: {component}, result keys: {list(component_result.keys())}")
                else:
                    logger.warning(f"No result for component: {component}")
            except Exception as e:
                logger.error(
                    f"Error processing component {component}: {str(e)}", exc_info=True)
                # Continue with other components rather than failing completely

        return results

    def _prepare_image_data(self, document_path: Optional[str]) -> Optional[Dict[str, str]]:
        """Prepare image data for API calls"""
        if not document_path or not os.path.exists(document_path):
            return None

        try:
            file_ext = os.path.splitext(document_path)[1].lower()

            # Handle image files
            if file_ext in ['.jpg', '.jpeg', '.png', '.gif']:
                logger.info(f"Preparing image data from file: {document_path}")
                return {
                    "base64": self._encode_image(document_path),
                    "media_type": self._get_media_type(document_path)
                }

            # Handle PDF files - convert first page to image
            elif file_ext == '.pdf':
                try:
                    from pdf2image import convert_from_path
                    logger.info(
                        f"Converting first page of PDF to image: {document_path}")
                    images = convert_from_path(
                        document_path, first_page=1, last_page=1)

                    if images:
                        # Save first page as temporary image
                        temp_image_path = f"{document_path}_page1.jpg"
                        images[0].save(temp_image_path, "JPEG")
                        logger.info(
                            f"PDF first page converted to: {temp_image_path}")

                        # Encode the converted image
                        image_data = {
                            "base64": self._encode_image(temp_image_path),
                            "media_type": "image/jpeg"
                        }

                        # Clean up temp image
                        try:
                            os.remove(temp_image_path)
                        except Exception as e:
                            logger.warning(
                                f"Failed to remove temp image: {str(e)}")

                        return image_data
                except Exception as e:
                    logger.error(f"Failed to convert PDF to image: {str(e)}")

            return None
        except Exception as e:
            logger.error(f"Error preparing image data: {str(e)}")
            return None

    def _encode_image(self, image_path: str) -> str:
        """Encode an image file to base64 string"""
        try:
            with open(image_path, "rb") as image_file:
                return base64.b64encode(image_file.read()).decode("utf-8")
        except Exception as e:
            logger.error(f"Failed to encode image {image_path}: {str(e)}")
            raise

    def _get_media_type(self, file_path: str) -> str:
        """Determine media type from file path"""
        ext = os.path.splitext(file_path.lower())[1]
        if ext == '.jpg' or ext == '.jpeg':
            return 'image/jpeg'
        elif ext == '.png':
            return 'image/png'
        elif ext == '.gif':
            return 'image/gif'
        elif ext == '.pdf':
            return 'application/pdf'
        return 'application/octet-stream'

    def _get_component_prompt(self, component: str, filename: str, metadata: Optional[Dict] = None) -> Optional[Dict]:
        """Get prompt for specific component"""
        if not hasattr(self, 'prompt_manager') or not self.prompt_manager:
            self.prompt_manager = PromptManager()

        # Map component names to prompt manager methods
        component_methods = {
            "metadata": self.prompt_manager.get_core_metadata_prompt,
            "classification": self.prompt_manager.get_classification_prompt,
            "entities": self.prompt_manager.get_entity_prompt,
            "text": self.prompt_manager.get_text_extraction_prompt,
            "design": self.prompt_manager.get_design_elements_prompt,
            "keywords": self.prompt_manager.get_taxonomy_keyword_prompt,
            "communication": self.prompt_manager.get_communication_focus_prompt
        }

        if component in component_methods:
            method = component_methods[component]
            # Call the method with filename and optional metadata
            if component == "metadata":
                return method(filename)
            else:
                return method(filename, metadata)

        return None

    def _call_claude_api_sync(self, prompt, image_data=None, max_retries=3):
        """Synchronous wrapper for Claude API calls with correct message formatting"""
        retry_count = 0
        last_error = None

        while retry_count < max_retries:
            try:
                # Create client with timeout
                with httpx.Client(timeout=60.0) as client:
                    # Prepare request payload
                    request_payload = {
                        "model": self.model,
                        "max_tokens": 4096,
                        "temperature": 0,
                        "messages": []
                    }

                    # Handle system message properly as a top-level parameter
                    if isinstance(prompt, dict) and "system" in prompt:
                        request_payload["system"] = prompt["system"]

                    # Add user message with optional image
                    user_content = []

                    # Handle different prompt formats
                    if isinstance(prompt, dict) and "user" in prompt:
                        user_text = prompt["user"]
                    elif isinstance(prompt, str):
                        user_text = prompt
                    else:
                        user_text = str(prompt)

                    user_content.append({
                        "type": "text",
                        "text": user_text
                    })

                    # Add image if available
                    if image_data and isinstance(image_data, dict) and "base64" in image_data:
                        user_content.append({
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": image_data.get("media_type", "image/jpeg"),
                                "data": image_data["base64"]
                            }
                        })

                    # Add user message to the messages array
                    request_payload["messages"].append({
                        "role": "user",
                        "content": user_content
                    })

                    # Make request
                    logger.info(
                        f"Sending request to Claude API for {self.model}")
                    response = client.post(
                        "https://api.anthropic.com/v1/messages",
                        headers=self.headers,
                        json=request_payload
                    )

                    # If error response, try to get more details
                    if response.status_code != 200:
                        error_detail = "No details available"
                        try:
                            error_json = response.json()
                            error_detail = error_json.get('error', {}).get(
                                'message', 'No details available')
                        except:
                            pass
                        logger.error(
                            f"API returned {response.status_code}: {error_detail}")
                        raise Exception(
                            f"API error: {response.status_code} - {error_detail}")

                    # Process response
                    data = response.json()

                    # Process response content
                    content = data.get('content', [])
                    message_text = ""
                    for block in content:
                        if block.get('type') == 'text':
                            message_text += block.get('text', '')

                    # Log response summary for debugging
                    if message_text:
                        preview = message_text[:200] + \
                            "..." if len(message_text) > 200 else message_text
                        logger.info(
                            f"Received response from Claude (preview): {preview}")
                    else:
                        logger.warning("Received empty response from Claude")

                    # Extract JSON
                    try:
                        # Try to find valid JSON in the response
                        json_matches = []

                        # Look for JSON within the entire text first
                        try:
                            result = json.loads(message_text)
                            return result
                        except json.JSONDecodeError:
                            # Not valid JSON, continue with partial extraction
                            pass

                        # Find all potential JSON objects
                        depth = 0
                        start_idx = None

                        for i, char in enumerate(message_text):
                            if char == '{' and start_idx is None:
                                start_idx = i
                                depth = 1
                            elif char == '{' and start_idx is not None:
                                depth += 1
                            elif char == '}' and start_idx is not None:
                                depth -= 1
                                if depth == 0:
                                    json_candidate = message_text[start_idx:i+1]
                                    try:
                                        json_obj = json.loads(json_candidate)
                                        json_matches.append(json_obj)
                                    except:
                                        pass
                                    start_idx = None

                        # If we found any valid JSON objects
                        if json_matches:
                            # Return the first valid match
                            return json_matches[0]

                        # If we get here, no valid JSON was found
                        logger.error("No valid JSON found in response")
                        retry_count += 1
                        time.sleep(2)
                        continue

                    except Exception as e:
                        logger.error(f"Error extracting JSON: {str(e)}")
                        retry_count += 1
                        time.sleep(2)
                        continue

            except httpx.HTTPStatusError as e:
                logger.error(f"API call error: {str(e)}")
                retry_count += 1
                last_error = str(e)
                time.sleep(2 * retry_count)  # Exponential backoff
                continue

            except Exception as e:
                logger.error(f"API call error: {str(e)}")
                retry_count += 1
                last_error = str(e)
                time.sleep(2 * retry_count)  # Exponential backoff
                continue

        # If we get here, all retries failed
        raise Exception(
            f"API call failed after {max_retries} attempts. Last error: {last_error}")

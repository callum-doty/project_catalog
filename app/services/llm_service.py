import os
import json
import httpx
import time
import base64
from typing import Dict, Any, List, Optional
from app.services.analysis_prompt import get_analysis_prompt
from celery.utils.log import get_task_logger
import backoff
from app.constants import MODEL_SETTINGS, ERROR_MESSAGES

try:
    import backoff
    BACKOFF_AVAILABLE = True
except ImportError:
    BACKOFF_AVAILABLE = False
    
def apply_backoff_decorator(func):
    if BACKOFF_AVAILABLE:
        return backoff.on_exception(
            backoff.expo,
            (httpx.RequestError, httpx.TimeoutException),
            max_tries=5,
            max_time=300
        )(func)
    return func


logger = get_task_logger(__name__)


class LLMService:
    def __init__(self):
        self.api_key = os.getenv("CLAUDE_API_KEY")
        if not self.api_key:
            raise ValueError(ERROR_MESSAGES['AUTHENTICATION_FAILED'])
        
        self.headers = {
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
            "x-api-key": self.api_key
        }
        
        # Default to the Claude 3 Opus model
        self.model = os.getenv("CLAUDE_MODEL", MODEL_SETTINGS['CLAUDE']['MODEL'])
        logger.info(f"Using Claude model: {self.model}")

    def _encode_image(self, image_path: str) -> str:
        """Encode an image file to base64 string"""
        try:
            with open(image_path, "rb") as image_file:
                return base64.b64encode(image_file.read()).decode("utf-8")
        except Exception as e:
            logger.error(f"Failed to encode image {image_path}: {str(e)}")
            raise

    def _get_file_data(self, filename: str) -> Optional[Dict[str, Any]]:
        """Get file data and path from storage if available"""
        try:
            from app.services.storage_service import MinIOStorage
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

    # Apply backoff decorator if available, otherwise just define the method normally
    def apply_backoff_decorator(func):
        if BACKOFF_AVAILABLE:
            return backoff.on_exception(
                backoff.expo,
                (httpx.RequestError, httpx.TimeoutException),
                max_tries=5,
                max_time=300
            )(func)
        return func
        
    @apply_backoff_decorator
    def analyze_document(self, filename: str, document_path: Optional[str] = None, max_retries: int = 3) -> Dict[Any, Any]:
        """Analyze document using Claude API with structured prompt and improved error handling"""
        logger.info(f"Starting analysis for document: {filename}")
        
        # If document path not provided, try to fetch from storage
        if not document_path:
            file_info = self._get_file_data(filename)
            if file_info and file_info.get("exists"):
                document_path = file_info.get("path")
                logger.info(f"Using document path from storage: {document_path}")
        
        # Get the enhanced analysis prompt
        analysis_prompt = get_analysis_prompt(filename)
        
        # Add an enhanced prefix to ensure proper formatting
        enhanced_prompt = (
            f"{analysis_prompt}\n\n"
            "Important: Your response must be a valid JSON object exactly matching "
            "the format above. Do not include any explanation or additional text "
            "outside of the JSON structure."
        )
        
        # Log truncated prompt for debugging
        logger.info(f"Using analysis prompt (truncated): {enhanced_prompt[:200]}...")
        
        # Prepare for API call with image if available
        includes_image = False
        base64_image = None
        media_type = None
        
        if document_path and os.path.exists(document_path):
            try:
                file_ext = os.path.splitext(document_path)[1].lower()
                if file_ext in ['.jpg', '.jpeg', '.png', '.gif']:
                    logger.info(f"Including image in analysis: {document_path}")
                    base64_image = self._encode_image(document_path)
                    media_type = self._get_media_type(document_path)
                    includes_image = True
                    logger.info(f"Successfully encoded image with media type: {media_type}")
                
                elif file_ext == '.pdf':
                    # For PDFs, try to convert first page to image
                    try:
                        from pdf2image import convert_from_path
                        logger.info(f"Converting first page of PDF to image: {document_path}")
                        images = convert_from_path(document_path, first_page=1, last_page=1)
                        if images:
                            # Save first page as temporary image
                            temp_image_path = f"{document_path}_page1.jpg"
                            images[0].save(temp_image_path, "JPEG")
                            logger.info(f"PDF first page converted to: {temp_image_path}")
                            
                            # Encode the converted image
                            base64_image = self._encode_image(temp_image_path)
                            media_type = "image/jpeg"
                            includes_image = True
                            logger.info(f"Successfully encoded PDF first page as image")
                            
                            # Clean up temp image after encoding
                            try:
                                os.remove(temp_image_path)
                            except:
                                pass
                    except Exception as e:
                        logger.error(f"Failed to convert PDF to image: {str(e)}")
            except Exception as e:
                logger.error(f"Failed to prepare image for request: {str(e)}")
        
        retry_count = 0
        last_error = None
        
        while retry_count < max_retries:
            try:
                logger.info(f"Making API request attempt {retry_count + 1}/{max_retries}")
                
                # Create the request payload based on whether we have an image
                if includes_image and base64_image and media_type:
                    response = self._make_multimodal_request(enhanced_prompt, base64_image, media_type)
                else:
                    # Text-only request with fallback to simpler structure
                    response = self._make_text_request(enhanced_prompt)
                
                # If we get here, we have a successful result
                return response
                        
            except httpx.TimeoutException as e:
                logger.error(f"Request timeout: {str(e)}")
                if retry_count < max_retries - 1:
                    retry_count += 1
                    time.sleep(2 ** retry_count)  # Exponential backoff
                    last_error = f"Request timeout: {str(e)}"
                    continue
                raise
                
            except httpx.HTTPStatusError as e:
                logger.error(f"HTTP status error: {str(e)}")
                # If we get a 400 error on messages endpoint, simplify request structure
                if "400 Bad Request" in str(e):
                    if retry_count < max_retries - 1:
                        logger.warning("Simplifying request format for next attempt")
                        retry_count += 1
                        time.sleep(2 ** retry_count)
                        last_error = f"Bad request error: {str(e)}"
                        continue
                    else:
                        # On last attempt, try text-only fallback
                        logger.warning("Trying text-only fallback on final attempt")
                        try:
                            logger.info("Making text-only fallback request")
                            response = self._make_text_request(enhanced_prompt, simplified=True)
                            return response
                        except Exception as fallback_error:
                            logger.error(f"Text-only fallback also failed: {str(fallback_error)}")
                            raise fallback_error
                
                if retry_count < max_retries - 1:
                    retry_count += 1
                    time.sleep(2 ** retry_count)  # Exponential backoff
                    last_error = f"HTTP error: {str(e)}"
                    continue
                raise
            
            except Exception as e:
                logger.error(f"Unexpected error: {str(e)}")
                if retry_count < max_retries - 1:
                    retry_count += 1
                    time.sleep(2 ** retry_count)
                    last_error = f"Unexpected error: {str(e)}"
                    continue
                raise
                
        # If we get here, all retries have been exhausted
        detailed_error = f"Max retries exceeded. Last error: {last_error if last_error else 'Unknown error'}"
        logger.error(detailed_error)
        raise Exception(detailed_error)

    def _make_multimodal_request(self, prompt: str, base64_image: str, media_type: str) -> Dict[Any, Any]:
        """Make a request that includes an image"""
        try:
            # Prepare messages payload with image
            messages = [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": prompt
                        },
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": media_type,
                                "data": base64_image
                            }
                        }
                    ]
                }
            ]
            
            # Create the full request payload
            request_payload = {
                "model": self.model,
                "messages": messages,
                "max_tokens": 4096,
                "temperature": 0
            }
            
            # Create a new client for each request
            with httpx.Client(
                base_url="https://api.anthropic.com",
                headers=self.headers,
                timeout=180.0  # Increased timeout for image processing
            ) as client:
                # Make the request
                response = client.post("/v1/messages", json=request_payload)
                logger.info(f"Multimodal request status: {response.status_code}")
                response.raise_for_status()
                
                # Process the response
                return self._process_messages_response(response)
                
        except Exception as e:
            logger.error(f"Error in multimodal request: {str(e)}")
            raise
    
    def _make_text_request(self, prompt: str, simplified=False) -> Dict[Any, Any]:
        """Make a text-only request, with optional simplified structure"""
        try:
            # Create a new client for each request
            with httpx.Client(
                base_url="https://api.anthropic.com",
                headers=self.headers,
                timeout=60.0
            ) as client:
                if simplified:
                    # Use a very simple structure for the request
                    request_payload = {
                        "model": self.model,
                        "messages": [{"role": "user", "content": prompt}],
                        "max_tokens": 4096
                    }
                else:
                    # Use standard structure
                    request_payload = {
                        "model": self.model,
                        "messages": [
                            {
                                "role": "system",
                                "content": "You are an expert document analyzer. Respond with valid JSON only."
                            },
                            {
                                "role": "user",
                                "content": [{"type": "text", "text": prompt}]
                            }
                        ],
                        "max_tokens": 4096,
                        "temperature": 0
                    }
                
                # Make the request
                response = client.post("/v1/messages", json=request_payload)
                logger.info(f"Text request status: {response.status_code}")
                
                # Log the response for debugging
                if response.status_code != 200:
                    logger.error(f"Text request error: {response.text}")
                
                response.raise_for_status()
                
                # Process the response
                return self._process_messages_response(response)
                
        except Exception as e:
            logger.error(f"Error in text-only request: {str(e)}")
            raise
    
    def _process_messages_response(self, response) -> Dict[Any, Any]:
        """Process a response from the messages API"""
        try:
            data = response.json()
            
            # Log successful response
            logger.info(f"Successfully received API response with ID: {data.get('id')}")
            
            # Process the response from the Messages API format
            content = data.get('content', [])
            
            # Extract text from the message content
            message_text = ""
            for block in content:
                if block.get('type') == 'text':
                    message_text += block.get('text', '')
            
            # Extract JSON from the response
            json_start = message_text.find('{')
            json_end = message_text.rfind('}') + 1
            
            if json_start >= 0 and json_end > json_start:
                json_str = message_text[json_start:json_end]
                try:
                    result = json.loads(json_str)
                    logger.info("Successfully parsed JSON response")
                    # Log a sample of the result for debugging
                    logger.info(f"Analysis result summary: {result.get('document_analysis', {}).get('summary', 'No summary available')}")
                    return result
                except json.JSONDecodeError as e:
                    logger.error(f"JSON parse error: {str(e)}")
                    logger.error(f"Failed JSON string (first 100 chars): {json_str[:100]}...")
                    raise ValueError("Failed to parse response as JSON")
            else:
                logger.error("No JSON object found in response")
                logger.error(f"Response text (first 100 chars): {message_text[:100]}...")
                raise ValueError("No JSON object found in response")
        
        except Exception as e:
            logger.error(f"Error processing response: {str(e)}")
            raise
    
    def _get_media_type(self, file_path: str) -> str:
        """Determine the media type based on file extension"""
        ext = os.path.splitext(file_path)[1].lower()
        if ext == '.jpg' or ext == '.jpeg':
            return 'image/jpeg'
        elif ext == '.png':
            return 'image/png'
        elif ext == '.gif':
            return 'image/gif'
        elif ext == '.pdf':
            return 'application/pdf'
        else:
            return 'application/octet-stream'
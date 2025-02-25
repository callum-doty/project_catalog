# app/services/llm_service.py

import os
import json
import httpx
import time
import base64
from typing import Dict, Any, List, Optional
from app.services.analysis_prompt import get_analysis_prompt
from celery.utils.log import get_task_logger

logger = get_task_logger(__name__)

class LLMService:
    def __init__(self):
        self.api_key = os.getenv("CLAUDE_API_KEY")
        if not self.api_key:
            raise ValueError("CLAUDE_API_KEY environment variable is not set")
        
        # Log key prefix for debugging (safely)
        if self.api_key:
            logger.info(f"Using Claude API key with prefix: {self.api_key[:4]}{'*' * (len(self.api_key) - 8)}{self.api_key[-4:]}")
        
        # Initialize headers with the updated Anthropic API version
        self.headers = {
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
            "x-api-key": self.api_key
        }

    def _encode_image(self, image_path: str) -> str:
        """Encode an image file to base64 string"""
        try:
            with open(image_path, "rb") as image_file:
                return base64.b64encode(image_file.read()).decode("utf-8")
        except Exception as e:
            logger.error(f"Failed to encode image {image_path}: {str(e)}")
            raise

    def analyze_document(self, filename: str, image_path: Optional[str] = None, max_retries: int = 3) -> Dict[Any, Any]:
        """Analyze document using Claude 3 API with structured prompt and retry logic"""
        logger.warning(f"Analyzing document: {filename}")
        
        # Get and enhance the analysis prompt
        base_prompt = get_analysis_prompt(filename)
        enhanced_prompt = (
            f"{base_prompt}\n\n"
            "Important: Your response must be a valid JSON object exactly matching "
            "the format above. Do not include any additional text or explanations "
            "outside of the JSON structure.\n\n"
            "Even if you don't have complete information, provide reasonable "
            "default values that match the required format. Always ensure your "
            "response is valid JSON."
        )

        # Prepare messages payload
        messages: List[Dict[str, Any]] = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": enhanced_prompt
                    }
                ]
            }
        ]
        
        # If image is provided, add it to the user message content
        if image_path:
            try:
                logger.info(f"Attempting to include image in analysis: {image_path}")
                base64_image = self._encode_image(image_path)
                # Add the image to the first user message content
                messages[0]["content"].append({
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": self._get_media_type(image_path),
                        "data": base64_image
                    }
                })
                logger.info(f"Successfully added image to the request: {image_path}")
            except Exception as e:
                logger.error(f"Failed to add image to request: {str(e)}")
                # Continue without the image if there's an error

        # Create the full request payload
        request_payload = {
            "model": "claude-3-opus-20240229",
            "messages": messages,
            "max_tokens": 4096,
            "temperature": 0,
            "system": "You are an expert document analyzer. Your task is to analyze documents and extract structured information about them. Always respond with a valid JSON object according to the specified format. Never include explanations or additional text outside the JSON object."
        }
        
        # Log the request structure (without the full image data)
        safe_payload = request_payload.copy()
        if image_path and len(messages[0]["content"]) > 1:
            # Replace image data with placeholder to avoid huge logs
            safe_payload["messages"][0]["content"][1]["source"]["data"] = "[BASE64_IMAGE_DATA]"
        logger.info(f"Request payload structure: {json.dumps(safe_payload)}")

        retry_count = 0
        last_error = None
        
        while retry_count < max_retries:
            try:
                # Create a new client for each request
                with httpx.Client(
                    base_url="https://api.anthropic.com",
                    headers=self.headers,
                    timeout=180.0  # Increased timeout for image processing
                ) as client:
                    
                    logger.info(f"Making API request attempt {retry_count + 1}/{max_retries}")
                    response = client.post(
                        "/v1/messages",
                        json=request_payload
                    )
                    
                    # Log the response status
                    logger.info(f"HTTP Request: POST {response.request.url} \"{response.status_code} {response.reason_phrase}\"")
                    
                    # Handle 401 (unauthorized)
                    if response.status_code == 401:
                        error_msg = f"API key unauthorized: {response.text}"
                        logger.error(error_msg)
                        raise ValueError(error_msg)
                        
                    # Handle 404 (endpoint not found)
                    if response.status_code == 404:
                        error_msg = f"API endpoint not found: {response.text}"
                        logger.error(error_msg)
                        raise ValueError(error_msg)
                    
                    # Handle 429 (rate limit)
                    if response.status_code == 429:
                        retry_after = int(response.headers.get('retry-after', '60'))
                        logger.warning(f"Rate limit hit, waiting {retry_after} seconds")
                        time.sleep(retry_after)
                        retry_count += 1
                        last_error = f"Rate limit exceeded: {response.text}"
                        continue
                    
                    # Handle 500+ errors (server errors)
                    if response.status_code >= 500:
                        logger.error(f"Server error: {response.status_code} - {response.text}")
                        if retry_count < max_retries - 1:
                            retry_count += 1
                            time.sleep(2 ** retry_count)  # Exponential backoff
                            last_error = f"Server error: {response.status_code} - {response.text}"
                            continue
                        raise ValueError(f"Server error after {max_retries} retries: {response.text}")
                        
                    # Handle other errors
                    response.raise_for_status()
                    data = response.json()
                    
                    # Log the response structure
                    logger.info(f"API response structure: {json.dumps(data, default=str)[:500]}...")
                    
                    # Process the response from the Messages API
                    content = data.get('content', [])
                    logger.info("Successfully received API response")
                    
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
                            return result
                        except json.JSONDecodeError as e:
                            logger.error(f"JSON parse error: {str(e)}")
                            logger.error(f"Failed JSON string: {json_str[:1000]}...")
                            if retry_count < max_retries - 1:
                                retry_count += 1
                                last_error = f"JSON parse error: {str(e)}"
                                continue
                            raise ValueError("Failed to parse response as JSON")
                    else:
                        logger.error("No JSON object found in response")
                        logger.error(f"Response text: {message_text[:1000]}...")
                        if retry_count < max_retries - 1:
                            retry_count += 1
                            last_error = "No JSON object found in response"
                            continue
                        raise ValueError("No JSON object found in response")
                        
            except httpx.TimeoutException as e:
                logger.error(f"Request timeout: {str(e)}")
                if retry_count < max_retries - 1:
                    retry_count += 1
                    time.sleep(2 ** retry_count)  # Exponential backoff
                    last_error = f"Request timeout: {str(e)}"
                    continue
                raise
                
            except httpx.HTTPError as e:
                logger.error(f"HTTP error: {str(e)}")
                if retry_count < max_retries - 1:
                    retry_count += 1
                    time.sleep(2 ** retry_count)  # Exponential backoff
                    last_error = f"HTTP error: {str(e)}"
                    continue
                raise
                
        # If we get here, all retries have been exhausted
        detailed_error = f"Max retries exceeded. Last error: {last_error if last_error else 'Unknown error'}"
        logger.error(detailed_error)
        raise Exception(detailed_error)
    
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
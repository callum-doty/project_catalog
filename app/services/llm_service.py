# app/services/llm_service.py

import os
import json
import httpx
import time
from typing import Dict, Any
from app.services.analysis_prompt import get_analysis_prompt
from celery.utils.log import get_task_logger

logger = get_task_logger(__name__)

class LLMService:
    def __init__(self):
        self.api_key = os.getenv("CLAUDE_API_KEY")
        if not self.api_key:
            raise ValueError("CLAUDE_API_KEY environment variable is not set")
        
        # Initialize the client but don't store it as an instance variable
        self.headers = {
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
            "x-api-key": self.api_key
        }

    def analyze_document(self, filename: str, max_retries: int = 3) -> Dict[Any, Any]:
        """Analyze document using Claude API with structured prompt and retry logic"""
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

        retry_count = 0
        while retry_count < max_retries:
            try:
                # Create a new client for each request
                with httpx.Client(
                    base_url="https://api.anthropic.com",
                    headers=self.headers,
                    timeout=60.0
                ) as client:
                    
                    logger.info(f"Making API request attempt {retry_count + 1}/{max_retries}")
                    response = client.post(
                        "/v1/complete",
                        json={
                            "model": "claude-2",
                            "prompt": f"\n\nHuman: {enhanced_prompt}\n\nAssistant: Here is the JSON analysis:\n",
                            "max_tokens_to_sample": 4096,
                            "temperature": 0,
                            "stream": False
                        }
                    )
                    
                    # Log the response status
                    logger.info(f"HTTP Request: POST {response.request.url} \"{response.status_code} {response.reason_phrase}\"")
                    
                    if response.status_code == 429:  # Rate limit
                        retry_after = int(response.headers.get('retry-after', '60'))
                        logger.warning(f"Rate limit hit, waiting {retry_after} seconds")
                        time.sleep(retry_after)
                        retry_count += 1
                        continue
                        
                    response.raise_for_status()
                    data = response.json()
                    
                    # Process the response
                    completion = data.get('completion', '').strip()
                    logger.info("Successfully received API response")
                    
                    # Extract JSON from the response
                    json_start = completion.find('{')
                    json_end = completion.rfind('}') + 1
                    
                    if json_start >= 0 and json_end > json_start:
                        json_str = completion[json_start:json_end]
                        try:
                            result = json.loads(json_str)
                            logger.info("Successfully parsed JSON response")
                            return result
                        except json.JSONDecodeError as e:
                            logger.error(f"JSON parse error: {str(e)}")
                            logger.error(f"Failed JSON string: {json_str[:1000]}...")
                            if retry_count < max_retries - 1:
                                retry_count += 1
                                continue
                            raise ValueError("Failed to parse response as JSON")
                    else:
                        logger.error("No JSON object found in response")
                        if retry_count < max_retries - 1:
                            retry_count += 1
                            continue
                        raise ValueError("No JSON object found in response")
                        
            except httpx.TimeoutException as e:
                logger.error(f"Request timeout: {str(e)}")
                if retry_count < max_retries - 1:
                    retry_count += 1
                    time.sleep(2 ** retry_count)  # Exponential backoff
                    continue
                raise
                
            except httpx.HTTPError as e:
                logger.error(f"HTTP error: {str(e)}")
                if retry_count < max_retries - 1:
                    retry_count += 1
                    time.sleep(2 ** retry_count)  # Exponential backoff
                    continue
                raise
                
        raise Exception("Max retries exceeded")
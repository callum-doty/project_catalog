# app/services/llm_service.py

import os
import json
import httpx
from typing import Dict, Any
from app.services.analysis_prompt import get_analysis_prompt

class LLMService:
    def __init__(self):
        api_key = os.getenv("CLAUDE_API_KEY")
        if not api_key:
            raise ValueError("CLAUDE_API_KEY environment variable is not set")
        
        self.client = httpx.Client(
            base_url="https://api.anthropic.com",
            headers={
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
                "x-api-key": api_key
            },
            timeout=60.0
        )

    def analyze_document(self, filename: str) -> Dict[Any, Any]:
        """Analyze document using Claude API with structured prompt"""
        try:
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
            
            print(f"Analyzing document: {filename}")
            
            # Make request with retry logic
            for attempt in range(3):
                try:
                    response = self.client.post(
                        "/v1/complete",
                        json={
                            "model": "claude-2",
                            "prompt": f"\n\nHuman: {enhanced_prompt}\n\nAssistant: Here is the JSON analysis:\n",
                            "max_tokens_to_sample": 4096,
                            "temperature": 0,
                            "stream": False
                        }
                    )
                    response.raise_for_status()
                    
                    data = response.json()
                    completion = data.get('completion', '').strip()
                    print(f"Raw response from Claude: {completion[:1000]}...")  # Print first 1000 chars
                    
                    # Try to extract JSON from the response
                    try:
                        # Remove any leading/trailing text that might be around the JSON
                        json_start = completion.find('{')
                        json_end = completion.rfind('}') + 1
                        
                        if json_start >= 0 and json_end > json_start:
                            json_str = completion[json_start:json_end]
                            print(f"Extracted JSON string: {json_str[:1000]}...")  # Print first 1000 chars
                            result = json.loads(json_str)
                            print("Successfully parsed JSON response")
                            return result
                        else:
                            print("No JSON object found in response. Response starts with:", completion[:100])
                            if attempt < 2:
                                print(f"Retrying request (attempt {attempt + 2}/3)...")
                                continue
                            raise ValueError("No JSON object found in response")
                            
                    except json.JSONDecodeError as e:
                        print(f"JSON parse error: {str(e)}")
                        print(f"Failed JSON string: {json_str[:1000]}...")  # Print first 1000 chars
                        if attempt < 2:
                            print(f"Retrying request (attempt {attempt + 2}/3)...")
                            continue
                        raise ValueError("Failed to parse response as JSON")
                    
                except httpx.TimeoutException:
                    if attempt < 2:
                        print(f"Request timed out. Retrying (attempt {attempt + 2}/3)...")
                        continue
                    raise
                
                except httpx.HTTPError as e:
                    print(f"HTTP error: {str(e)}")
                    if attempt < 2:
                        print(f"Retrying request (attempt {attempt + 2}/3)...")
                        continue
                    raise
                    
        except Exception as e:
            print(f"LLM analysis error: {str(e)}")
            raise Exception(f"LLM analysis failed: {str(e)}")
        
        finally:
            self.client.close()
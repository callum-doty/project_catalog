import os
import json
from anthropic import Anthropic
from typing import Dict, Any

class LLMService:
    def __init__(self):
        self.api_key = os.getenv("CLAUDE_API_KEY")
        self.client = Anthropic(
            api_key=self.api_key,
            base_url="https://api.anthropic.com",
            timeout=60.0,
        )

    def analyze_text(self, text: str, prompt_template: str) -> Dict[Any, Any]:
        """Analyze text using Claude API"""
        try:
            # Prepare the message
            message = f"{prompt_template}\n\nDocument Content:\n{text}"
            
            # Call Claude API
            response = self.client.messages.create(
                model="claude-3-opus-20240229",
                max_tokens=4096,
                messages=[{
                    "role": "user",
                    "content": message
                }]
            )
            
            # Extract and validate JSON response
            try:
                response_text = response.content[0].text
                return json.loads(response_text)
            except json.JSONDecodeError:
                raise ValueError("Failed to parse Claude's response as JSON")

        except Exception as e:
            raise Exception(f"LLM analysis failed: {str(e)}")

    def extract_text(self, file_content: bytes) -> str:
        """
        Basic text extraction (placeholder for more sophisticated extraction)
        """
        try:
            return file_content.decode("utf-8", errors="ignore")
        except Exception as e:
            raise Exception(f"Text extraction failed: {str(e)}")
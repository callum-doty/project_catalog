# app/services/analysis_prompt.py

def get_analysis_prompt(filename: str) -> str:
    """
    Generate a structured analysis prompt optimized for Claude 3 with enhanced image analysis capabilities
    """
    return f"""Please analyze the document or image '{filename}' and provide a structured analysis in the exact format specified below.

If an image is provided, carefully analyze all visual elements, text content, colors, themes, and design patterns. Look for elements that indicate a campaign, geographic targeting, or demographic focus.

Required Output Format:
{{
    "document_analysis": {{
        "summary": "Brief 1-2 sentence overview as a single string",
        "confidence_score": <float between 0.0 and 1.0>,
        "file_type": "identify if mailer/digital/etc - as a single string",
        "campaign_type": "primary/general/special/runoff - as a single string"
    }},
    
    "design_elements": {{
        "color_scheme": ["primary color", "secondary color", "accent color"],
        "theme": "main visual theme as a single string",
        "mail_piece_type": "type of mailer/asset as a single string",
        "geographic_location": "target geography as City, State or State only",
        "target_audience": "specific demographic focus as a single string",
        "campaign_name": "campaign identifier as a single string",
        "confidence": <float between 0.0 and 1.0>
    }},
    
    "classification": {{
        "category": "main category as a single string",
        "confidence": <float between 0.0 and 1.0>
    }},
    
    "extracted_text": {{
        "main_message": "primary text/headline as a single string - DO NOT return as a list",
        "supporting_text": "secondary messages as a single string - DO NOT return as a list",
        "call_to_action": "CTA text if present as a single string",
        "confidence": <float between 0.0 and 1.0>
    }},
    
    "keywords": [
        {{
            "text": "keyword1 as a single string",
            "category": "theme/visual/messaging/demographic as a single string",
            "confidence": <float between 0.0 and 1.0>
        }},
        {{
            "text": "keyword2 as a single string",
            "category": "theme/visual/messaging/demographic as a single string",
            "confidence": <float between 0.0 and 1.0>
        }},
        ... maximum 5 keywords total
    ]
}}

Important Requirements:
1. All text fields MUST be single strings, not lists or arrays
2. All confidence scores MUST be floats between 0.0 and 1.0
3. Exactly 5 keywords maximum, prioritizing most relevant/distinctive
4. Color schemes MUST use standardized color names
5. Geographic locations MUST use standardized format (City, State or State only)
6. All fields are required - provide reasonable default values if information is unclear
7. Response MUST be valid JSON and match this exact schema
8. DO NOT include any explanation or additional text outside the JSON structure
9. For images: carefully transcribe any visible text, identify logos, and analyze visual elements
10. For confidence scores: higher values (closer to 1.0) indicate greater certainty about your analysis"""
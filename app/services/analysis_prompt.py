def get_analysis_prompt(filename: str) -> str:
    """
    Generate a structured analysis prompt that maps directly to database schema
    """
    return f"""Please analyze the document '{filename}' and provide a structured analysis in the exact format specified below.
Required Output Format:
{{
    "document_analysis": {{
        "summary": "Brief 1-2 sentence overview",
        "confidence_score": <float between 0.0 and 1.0>,
        "file_type": "identify if mailer/digital/etc",
        "campaign_type": "primary/general/special/runoff"
    }},
    
    "design_elements": {{
        "color_scheme": ["primary color", "secondary color", "accent color"],
        "theme": "main visual theme",
        "mail_piece_type": "type of mailer/asset",
        "geographic_location": "target geography",
        "target_audience": "specific demographic focus",
        "campaign_name": "campaign identifier",
        "confidence": <float between 0.0 and 1.0>
    }},
    
    "classification": {{
        "category": "main category",
        "confidence": <float between 0.0 and 1.0>,
        "subcategories": ["subcategory1", "subcategory2"],
        "tags": ["tag1", "tag2", "tag3"]
    }},
    
    "extracted_text": {{
        "main_message": "primary text/headline",
        "supporting_text": "secondary messages",
        "call_to_action": "CTA text if present",
        "confidence": <float between 0.0 and 1.0>
    }},
    
    "keywords": [
        {{
            "text": "keyword1",
            "category": "theme/visual/messaging/demographic",
            "confidence": <float between 0.0 and 1.0>
        }},
        // limit to 5 most relevant keywords
    ]
}}
Please ensure:
1. All confidence scores are between 0.0 and 1.0
2. Exactly 5 keywords maximum, prioritizing most relevant/distinctive
3. Color schemes use standardized color names
4. Categories align with the existing classification system
5. Geographic locations use standardized format (City, State or State only)"""
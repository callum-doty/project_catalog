
def get_analysis_prompt(filename: str) -> str:
   """
   Generate a structured analysis prompt optimized for Claude with enhanced political document analysis capabilities
   """
   return f"""Analyze the document or image '{filename}' carefully and provide a structured analysis in the exact JSON format specified below.


For this analysis:
1. Carefully examine ALL text present in the document
2. Pay special attention to names of politicians, political parties, campaign slogans, and election types
3. Look for dates and years to determine the specific election cycle
4. Analyze visual elements like colors, imagery, and design that convey political messaging
5. Determine if the document is supportive/positive or opposing/negative toward the subject
6. Identify the specific geographic target of the document (state, district, national)
7. Note any specific policy positions or issues mentioned
8. Identify both the client/candidate and any opponent mentioned
9. Look for survey questions or public opinion trends
10. Note the file naming convention and any identifiers in the filename


Required Output Format:
{{
   "document_analysis": {{
       "summary": "Clear 1-2 sentence overview that accurately identifies the candidate, election type, year, and main message",
       "confidence_score": <float between 0.0 and 1.0>,
       "file_type": "mailer/digital/handout/poster/etc.",
       "campaign_type": "primary/general/special/runoff",
       "election_year": "Specify the exact year if identifiable, otherwise your best estimate",
       "document_tone": "positive/negative/neutral/informational"
   }},
  
   "design_elements": {{
       "color_scheme": ["primary color", "secondary color", "accent color"],
       "theme": "patriotic/conservative/progressive/etc.",
       "mail_piece_type": "postcard/letter/brochure/door hanger/etc.",
       "geographic_location": "City, State or State only",
       "target_audience": "specific demographic focus (republicans, democrats, veterans, etc.)",
       "campaign_name": "candidate and position sought (e.g., 'Smith for Senate')",
       "visual_elements": ["flag", "candidate photo", "family", "etc."],
       "confidence": <float between 0.0 and 1.0>
   }},
  
   "classification": {{
       "category": "GOTV/attack/comparison/endorsement/issue/biographical",
       "confidence": <float between 0.0 and 1.0>
   }},
  
   "entities": {{
       "client_name": "full name of the client/candidate",
       "opponent_name": "full name of any opponent mentioned, if applicable",
       "creation_date": "date created or date shown on document if available",
       "survey_question": "any survey questions shown, if applicable",
       "file_identifier": "any naming convention or identifier visible in the document"
   }},
  
   "extracted_text": {{
       "main_message": "primary headline/slogan as a single string",
       "supporting_text": "secondary messages as a single string",
       "call_to_action": "specific voter instruction if present (e.g., 'Vote on Nov 8')",
       "candidate_name": "full name of the primary candidate",
       "opponent_name": "full name of any opponent mentioned, if applicable",
       "confidence": <float between 0.0 and 1.0>
   }},
  
   "communication_focus": {{
       "primary_issue": "the main policy issue or focus of the communication",
       "secondary_issues": ["list", "of", "other", "issues", "mentioned"],
       "messaging_strategy": "attack/positive/comparison/etc."
   }},
  
   "keywords": [
       {{
           "text": "keyword1 as a single string",
           "category": "candidate/opponent/issue/visual/location/audience/theme",
           "confidence": <float between 0.0 and 1.0>
       }},
       {{
           "text": "keyword2 as a single string",
           "category": "candidate/opponent/issue/visual/location/audience/theme",
           "confidence": <float between 0.0 and 1.0>
       }},
       ... maximum 10 keywords total
   ]
}}


Critical Requirements:
1. ALL text fields MUST be single strings, not lists or arrays
2. ALL confidence scores MUST be floats between 0.0 and 1.0
3. ALWAYS include exactly 10 keywords maximum, prioritizing the most relevant terms
4. NEVER guess information that conflicts with visible text in the document
5. ALWAYS accurately identify the candidate being supported or opposed
6. ALWAYS accurately identify the election year when possible
7. ALWAYS specify the correct election type (primary/general)
8. ALWAYS identify if document is positive (supporting) or negative (opposing)
9. CAREFULLY transcribe ALL visible text when analyzing images
10. ALWAYS include the candidate name, geographic location, and visual theme in the keywords
11. Response MUST be valid JSON and match this exact schema"""

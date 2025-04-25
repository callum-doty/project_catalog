# app/services/prompt_manager.py
import os
from datetime import datetime

class PromptManager:
    """Manager for document analysis prompts with modular components"""
    
    def __init__(self):
        self.model_capabilities = self._get_model_capabilities()
        self.base_system_prompt = """You are an expert document analyzer specializing in political and campaign materials. 
Provide accurate, objective analysis in the exact JSON format requested."""
    
    def _get_model_capabilities(self):
        """Get capabilities based on configured model"""
        model = os.getenv("CLAUDE_MODEL", "claude-3-opus-20240229")
        
        # Different capabilities based on model
        if "claude-3-opus" in model:
            return {
                "vision": True,
                "structure": "high",
                "detail": "high"
            }
        elif "claude-3-sonnet" in model:
            return {
                "vision": True,
                "structure": "medium",
                "detail": "medium"
            }
        else:
            return {
                "vision": True,
                "structure": "basic",
                "detail": "basic"
            }
    
    def get_core_metadata_prompt(self, filename):
        """Generate a prompt for basic document metadata analysis"""
        return {
            "system": self.base_system_prompt,
            "user": f"""Analyze the document '{filename}' and provide ONLY the following core metadata in JSON format:

{{
  "document_analysis": {{
    "summary": "Clear 1-2 sentence overview of the document",
    "confidence_score": <float between 0.0 and 1.0>,
    "document_type": "mailer/digital/handout/poster/etc.",
    "campaign_type": "primary/general/special/runoff",
    "election_year": "Specify the exact year if identifiable",
    "document_tone": "positive/negative/neutral/informational"
  }}
}}

Focus ONLY on these core metadata elements. Your response MUST be valid JSON.
"""
        }
    
    def get_classification_prompt(self, filename, metadata=None):
        """Generate a prompt for document classification"""
        context = ""
        if metadata:
            context = f"""Based on prior analysis, this is a {metadata.get('document_type', '')} 
from {metadata.get('election_year', '')} that appears to be {metadata.get('document_tone', '')}.
"""
        
        return {
            "system": self.base_system_prompt,
            "user": f"""{context}Analyze the document '{filename}' and determine its primary category and purpose.

Return ONLY the following JSON:

{{
  "classification": {{
    "category": "GOTV/attack/comparison/endorsement/issue/biographical",
    "subcategory": "specific issue or narrower category",
    "confidence": <float between 0.0 and 1.0>,
    "rationale": "Brief explanation of classification"
  }}
}}

Your response MUST be valid JSON formatted exactly as requested above.
"""
        }
    
    def get_entity_prompt(self, filename, metadata=None):
        """Generate a prompt for entity extraction"""
        context = ""
        if metadata:
            context = f"""Based on prior analysis, this is a {metadata.get('document_type', '')} 
from {metadata.get('election_year', '')} that appears to be {metadata.get('document_tone', '')}.
"""
        
        return {
            "system": self.base_system_prompt,
            "user": f"""{context}Analyze the document '{filename}' and extract entity information.

Return ONLY the following JSON:

{{
  "entities": {{
    "client_name": "full name of the client/candidate",
    "opponent_name": "full name of any opponent mentioned, if applicable",
    "creation_date": "date created or date shown on document if available",
    "survey_question": "any survey questions shown, if applicable",
    "file_identifier": "any naming convention or identifier visible in the document",
    "confidence": <float between 0.0 and 1.0>
  }}
}}

Your response MUST be valid JSON formatted exactly as requested above.
"""
        }
    
    def get_text_extraction_prompt(self, filename, metadata=None):
        """Generate a prompt for text extraction"""
        context = ""
        if metadata:
            context = f"""Based on prior analysis, this is a {metadata.get('document_type', '')} 
from {metadata.get('election_year', '')}.
"""
        
        return {
            "system": self.base_system_prompt,
            "user": f"""{context}Analyze the document '{filename}' and extract the text content.

Return ONLY the following JSON:

{{
  "extracted_text": {{
    "main_message": "primary headline/slogan as a single string",
    "supporting_text": "secondary messages as a single string",
    "call_to_action": "specific voter instruction if present (e.g., 'Vote on Nov 8')",
    "candidate_name": "full name of the primary candidate",
    "opponent_name": "full name of any opponent mentioned, if applicable",
    "confidence": <float between 0.0 and 1.0>
  }}
}}

Your response MUST be valid JSON formatted exactly as requested above.
"""
        }
    
    def get_design_elements_prompt(self, filename, metadata=None):
        """Generate a prompt for design element analysis"""
        context = ""
        if metadata:
            context = f"""Based on prior analysis, this is a {metadata.get('document_type', '')} 
from {metadata.get('election_year', '')}.
"""
        
        return {
            "system": self.base_system_prompt,
            "user": f"""{context}Analyze the visual design elements in the document '{filename}'.

Return ONLY the following JSON:

{{
  "design_elements": {{
    "color_scheme": ["primary color", "secondary color", "accent color"],
    "theme": "patriotic/conservative/progressive/etc.",
    "mail_piece_type": "postcard/letter/brochure/door hanger/etc.",
    "geographic_location": "City, State or State only",
    "target_audience": "specific demographic focus (republicans, democrats, veterans, etc.)",
    "campaign_name": "candidate and position sought (e.g., 'Smith for Senate')",
    "visual_elements": ["flag", "candidate photo", "family", "etc."],
    "confidence": <float between 0.0 and 1.0>
  }}
}}

Your response MUST be valid JSON formatted exactly as requested above.
"""
        }
    
    def get_taxonomy_keyword_prompt(self, filename, metadata=None):
        """Generate a prompt for hierarchical taxonomy keyword extraction"""
        context = ""
        if metadata:
            context = f"""Based on prior analysis, this is a {metadata.get('document_type', '')} 
from {metadata.get('election_year', '')} that appears to be {metadata.get('document_tone', '')}.
"""
        
        taxonomy_guidelines = """
Primary taxonomy categories and examples:
1. Policy Issues & Topics:
   - Economy & Taxes: taxes, inflation, jobs, wages, budget, deficit, trade
   - Social Issues: abortion, LGBTQ+ rights, marriage equality, religious freedom
   - Healthcare: Medicare, Medicaid, Obamacare, prescription drugs
   - Public Safety: crime, guns, police, immigration, border security
   - Environment: climate change, renewable energy, fossil fuels, conservation
   - Education: schools, college affordability, student loans, teachers
   - Government Reform: corruption, election integrity, voting rights, term limits

2. Candidate & Entity:
   - Candidate Elements: name, party, previous/current office, biography
   - Political Parties: Democratic, Republican, Independent, Progressive
   - Opposition Elements: opponent name, criticism, contrast points
   - External Endorsements: organizations, leaders, unions, celebrities

3. Communication Style:
   - Message Tone: positive, negative, contrast, attack, informational
   - Mail Piece Types: postcard, mailer, brochure, letter, push card
   - Message Focus: introduction, issue-based, biography, endorsement, GOTV
   - Visual Design: color scheme, photography, graphics, typography, layout

4. Geographic & Demographic:
   - Geographic Level: national, statewide, congressional, county, city
   - Target Audience: age group, gender, race/ethnicity, education, income

5. Campaign Context:
   - Election Type: general, primary, special, runoff, recall
   - Election Year: 2024, 2022, 2020, etc.
   - Office Sought: presidential, senate, house, governor, state, local
   - Campaign Phase: early campaign, late campaign, GOTV period
"""
        
        return {
            "system": self.base_system_prompt,
            "user": f"""{context}Analyze the document '{filename}' and identify relevant keywords using the hierarchical taxonomy system.

{taxonomy_guidelines}

Return ONLY the following JSON:

{{
  "hierarchical_keywords": [
    {{
      "specific_term": "specific term used in document (e.g., 'abortion', 'taxes', 'corruption')",
      "primary_category": "Choose from: Policy Issues & Topics | Candidate & Entity | Communication Style | Geographic & Demographic | Campaign Context",
      "subcategory": "appropriate subcategory from the taxonomy matching the primary_category",
      "synonyms": ["any", "synonyms", "or", "related", "terms"],
      "relevance_score": <float between 0.0 and 1.0>
    }},
    ... provide 10-15 hierarchical keywords total, ordered by relevance_score (highest first)
  ]
}}

Your response MUST be valid JSON formatted exactly as requested above.
"""
        }
    
    def get_communication_focus_prompt(self, filename, metadata=None):
        """Generate a prompt for communication focus analysis"""
        context = ""
        if metadata:
            context = f"""Based on prior analysis, this is a {metadata.get('document_type', '')} 
from {metadata.get('election_year', '')} that appears to be {metadata.get('document_tone', '')}.
"""
        
        return {
            "system": self.base_system_prompt,
            "user": f"""{context}Analyze the document '{filename}' and determine its primary communication focus and strategy.

Return ONLY the following JSON:

{{
  "communication_focus": {{
    "primary_issue": "the main policy issue or focus of the communication",
    "secondary_issues": ["list", "of", "other", "issues", "mentioned"],
    "messaging_strategy": "attack/positive/comparison/etc.",
    "audience_persuasion": "describe how the document attempts to persuade its audience",
    "confidence": <float between 0.0 and 1.0>
  }}
}}

Your response MUST be valid JSON formatted exactly as requested above.
"""
        }
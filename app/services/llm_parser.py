# app/services/llm_parser.py

from typing import Dict, Any, Optional
import json
from datetime import datetime

class LLMResponseParser:
    @staticmethod
    def validate_confidence(value: float) -> float:
        """Validate and normalize confidence scores"""
        try:
            value = float(value)
            return max(0.0, min(1.0, value))
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def parse_llm_analysis(data: Dict[str, Any]) -> Dict[str, Any]:
        """Parse and validate LLM analysis data"""
        analysis = data.get('document_analysis', {})
        return {
            'summary_description': analysis.get('summary', ''),
            'content_analysis': json.dumps(analysis),
            'confidence_score': LLMResponseParser.validate_confidence(
                analysis.get('confidence_score', 0.0)
            ),
            'analysis_date': datetime.utcnow(),
            'model_version': 'claude-3'
        }

    @staticmethod
    def parse_design_elements(data: Dict[str, Any]) -> Dict[str, Any]:
        """Parse and validate design elements data"""
        design = data.get('design_elements', {})
        return {
            'color_scheme': json.dumps(design.get('color_scheme', [])),
            'theme': design.get('theme', ''),
            'mail_piece_type': design.get('mail_piece_type', ''),
            'geographic_location': design.get('geographic_location', ''),
            'target_audience': design.get('target_audience', ''),
            'campaign_name': design.get('campaign_name', ''),
            'confidence': int(LLMResponseParser.validate_confidence(
                design.get('confidence', 0.0)
            ) * 100),
            'created_date': datetime.utcnow()
        }

    @staticmethod
    def parse_classification(data: Dict[str, Any]) -> Dict[str, Any]:
        """Parse and validate classification data"""
        classification = data.get('classification', {})
        return {
            'category': classification.get('category', ''),
            'confidence': int(LLMResponseParser.validate_confidence(
                classification.get('confidence', 0.0)
            ) * 100),
            'classification_date': datetime.utcnow()
        }

    @staticmethod
    def parse_keywords(data: Dict[str, Any]) -> list:
        """Parse and validate keywords data"""
        keywords = data.get('keywords', [])
        parsed_keywords = []
        
        for keyword in keywords[:5]:  # Limit to 5 keywords
            parsed_keywords.append({
                'keyword': keyword.get('text', ''),
                'category': keyword.get('category', ''),
                'relevance_score': int(LLMResponseParser.validate_confidence(
                    keyword.get('confidence', 0.0)
                ) * 100)
            })
            
        return parsed_keywords
# app/services/llm_parser.py

from typing import Dict, Any, Optional, List
import json
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class DateTimeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)

class LLMResponseParser:
    @staticmethod
    def validate_confidence(value: float) -> float:
        """Validate and normalize confidence scores"""
        try:
            value = float(value)
            return max(0.0, min(1.0, value))
        except (TypeError, ValueError):
            logger.warning(f"Invalid confidence value: {value}, defaulting to 0.0")
            return 0.0

    @staticmethod
    def ensure_string(value: Any, default: str = '') -> str:
        """Convert various types to string safely"""
        if isinstance(value, list):
            return ' '.join(str(item) for item in value)
        elif value is None:
            return default
        return str(value)

    @staticmethod
    def parse_llm_analysis(data: Dict[str, Any]) -> Dict[str, Any]:
        """Parse and validate LLM analysis data"""
        try:
            analysis = data.get('document_analysis', {})
            
            if not analysis:
                logger.warning("No document_analysis found in LLM response")
                analysis = {}
            
            result = {
                'summary_description': LLMResponseParser.ensure_string(analysis.get('summary', '')),
                'content_analysis': json.dumps(analysis),
                'confidence_score': LLMResponseParser.validate_confidence(
                    analysis.get('confidence_score', 0.0)
                ),
                'campaign_type': LLMResponseParser.ensure_string(analysis.get('campaign_type', '')),
                'election_year': LLMResponseParser.ensure_string(analysis.get('election_year', '')),
                'document_tone': LLMResponseParser.ensure_string(analysis.get('document_tone', '')),
                'analysis_date': datetime.utcnow(),
                'model_version': 'claude-3-opus-20240229'
            }
            
            # Log with custom encoder for datetime
            logger.info(f"Parsed LLM analysis: {json.dumps(result, cls=DateTimeEncoder)}")
            logger.info(f"Summary description: {result['summary_description']}")
            return result
            
        except Exception as e:
            logger.error(f"Error parsing LLM analysis: {str(e)}")
            raise

    @staticmethod
    def parse_design_elements(data: Dict[str, Any]) -> Dict[str, Any]:
        """Parse and validate design elements data"""
        try:
            design = data.get('design_elements', {})
            
            if not design:
                logger.warning("No design_elements found in LLM response")
                design = {}
            
            result = {
                'color_scheme': json.dumps(design.get('color_scheme', [])),
                'theme': LLMResponseParser.ensure_string(design.get('theme', '')),
                'mail_piece_type': LLMResponseParser.ensure_string(design.get('mail_piece_type', '')),
                'geographic_location': LLMResponseParser.ensure_string(design.get('geographic_location', '')),
                'target_audience': LLMResponseParser.ensure_string(design.get('target_audience', '')),
                'campaign_name': LLMResponseParser.ensure_string(design.get('campaign_name', '')),
                'visual_elements': json.dumps(design.get('visual_elements', [])),
                'confidence': int(LLMResponseParser.validate_confidence(
                    design.get('confidence', 0.0)
                ) * 100),
                'created_date': datetime.utcnow()
            }
            
            # Log with custom encoder for datetime
            logger.info(f"Parsed design elements: {json.dumps(result, cls=DateTimeEncoder)}")
            return result
            
        except Exception as e:
            logger.error(f"Error parsing design elements: {str(e)}")
            raise

    @staticmethod
    def parse_classification(data: Dict[str, Any]) -> Dict[str, Any]:
        """Parse and validate classification data"""
        try:
            classification = data.get('classification', {})
            
            if not classification:
                logger.warning("No classification found in LLM response")
                classification = {}
            
            result = {
                'category': LLMResponseParser.ensure_string(classification.get('category', '')),
                'confidence': int(LLMResponseParser.validate_confidence(
                    classification.get('confidence', 0.0)
                ) * 100),
                'classification_date': datetime.utcnow()
            }
            
            # Log with custom encoder for datetime
            logger.info(f"Parsed classification: {json.dumps(result, cls=DateTimeEncoder)}")
            return result
            
        except Exception as e:
            logger.error(f"Error parsing classification: {str(e)}")
            raise

    @staticmethod
    def parse_entity_info(data: Dict[str, Any]) -> Dict[str, Any]:
        """Parse and validate entity information"""
        try:
            entities = data.get('entities', {})
            
            if not entities:
                logger.warning("No entities found in LLM response")
                entities = {}
            
            result = {
                'client_name': LLMResponseParser.ensure_string(entities.get('client_name', '')),
                'opponent_name': LLMResponseParser.ensure_string(entities.get('opponent_name', '')),
                'creation_date': LLMResponseParser.ensure_string(entities.get('creation_date', '')),
                'survey_question': LLMResponseParser.ensure_string(entities.get('survey_question', '')),
                'file_identifier': LLMResponseParser.ensure_string(entities.get('file_identifier', '')),
                'created_date': datetime.utcnow()
            }
            
            logger.info(f"Parsed entity information: {json.dumps(result, cls=DateTimeEncoder)}")
            return result
            
        except Exception as e:
            logger.error(f"Error parsing entity information: {str(e)}")
            raise

    @staticmethod
    def parse_communication_focus(data: Dict[str, Any]) -> Dict[str, Any]:
        """Parse and validate communication focus data"""
        try:
            focus = data.get('communication_focus', {})
            
            if not focus:
                logger.warning("No communication_focus found in LLM response")
                focus = {}
            
            # Handle secondary_issues as a JSON array
            secondary_issues = focus.get('secondary_issues', [])
            if not isinstance(secondary_issues, list):
                secondary_issues = []
            
            result = {
                'primary_issue': LLMResponseParser.ensure_string(focus.get('primary_issue', '')),
                'secondary_issues': json.dumps(secondary_issues),
                'messaging_strategy': LLMResponseParser.ensure_string(focus.get('messaging_strategy', '')),
                'created_date': datetime.utcnow()
            }
            
            logger.info(f"Parsed communication focus: {json.dumps(result, cls=DateTimeEncoder)}")
            return result
            
        except Exception as e:
            logger.error(f"Error parsing communication focus: {str(e)}")
            raise

    @staticmethod
    def parse_extracted_text(data: Dict[str, Any]) -> Dict[str, Any]:
        """Parse and validate extracted text data"""
        try:
            text_data = data.get('extracted_text', {})
            
            if not text_data:
                logger.warning("No extracted_text found in LLM response")
                text_data = {}
            
            # Create a combined text content from main message and supporting text
            main_message = LLMResponseParser.ensure_string(text_data.get('main_message', ''))
            supporting_text = LLMResponseParser.ensure_string(text_data.get('supporting_text', ''))
            
            # Combine for backwards compatibility with existing field
            combined_text = f"{main_message}\n\n{supporting_text}"
            
            result = {
                'text_content': combined_text,
                'main_message': main_message,
                'supporting_text': supporting_text,
                'call_to_action': LLMResponseParser.ensure_string(text_data.get('call_to_action', '')),
                'candidate_name': LLMResponseParser.ensure_string(text_data.get('candidate_name', '')),
                'opponent_name': LLMResponseParser.ensure_string(text_data.get('opponent_name', '')),
                'confidence': int(LLMResponseParser.validate_confidence(
                    text_data.get('confidence', 0.0)
                ) * 100),
                'extraction_date': datetime.utcnow()
            }
            
            logger.info(f"Parsed extracted text: {json.dumps(result, cls=DateTimeEncoder)}")
            return result
            
        except Exception as e:
            logger.error(f"Error parsing extracted text: {str(e)}")
            raise

    @staticmethod
    def parse_keywords(data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Parse and validate keywords data"""
        try:
            keywords = data.get('keywords', [])
            parsed_keywords = []
            
            if not keywords:
                logger.warning("No keywords found in LLM response")
                return []
            
            logger.info(f"Processing {len(keywords)} keywords")
            
            for keyword in keywords[:10]:  # Limit to 10 keywords
                try:
                    keyword_text = LLMResponseParser.ensure_string(keyword.get('text', ''))
                    if not keyword_text:
                        logger.warning(f"Empty keyword text in {keyword}")
                        continue
                        
                    keyword_entry = {
                        'keyword': keyword_text,
                        'category': LLMResponseParser.ensure_string(keyword.get('category', '')),
                        'relevance_score': int(LLMResponseParser.validate_confidence(
                            keyword.get('confidence', 0.0)
                        ) * 100)
                    }
                    parsed_keywords.append(keyword_entry)
                    
                except Exception as e:
                    logger.error(f"Error parsing individual keyword {keyword}: {str(e)}")
                    continue
            
            logger.info(f"Successfully parsed {len(parsed_keywords)} keywords")
            return parsed_keywords
            
        except Exception as e:
            logger.error(f"Error parsing keywords: {str(e)}")
            raise
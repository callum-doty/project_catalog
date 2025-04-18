# app/services/llm_parser.py

from typing import Dict, Any, Optional, List
import json
from datetime import datetime
import logging
from app.models.keyword_models import KeywordTaxonomy, KeywordSynonym, DocumentKeyword
from app.extensions import db

logger = logging.getLogger(__name__)

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
        """Parse and validate basic LLM analysis data"""
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
            
            logger.info(f"Parsed basic LLM analysis with summary: {result['summary_description'][:50]}...")
            return result
            
        except Exception as e:
            logger.error(f"Error parsing LLM analysis: {str(e)}")
            raise

    @staticmethod
    def parse_hierarchical_keywords(data: Dict[str, Any], document_id: int) -> List[DocumentKeyword]:
        """
        Parse hierarchical keywords and map to taxonomy.
        Returns a list of DocumentKeyword objects ready to be added to the database.
        """
        try:
            # Get hierarchical keywords from response
            hierarchical_keywords = data.get('hierarchical_keywords', [])
            if not hierarchical_keywords:
                logger.warning("No hierarchical_keywords found in LLM response")
                return []
            
            logger.info(f"Processing {len(hierarchical_keywords)} hierarchical keywords")
            document_keywords = []
            
            for kw in hierarchical_keywords[:10]:  # Limit to 10 keywords max
                try:
                    specific_term = LLMResponseParser.ensure_string(kw.get('specific_term', ''))
                    if not specific_term:
                        logger.warning(f"Empty specific_term in keyword: {kw}")
                        continue
                    
                    primary_category = LLMResponseParser.ensure_string(kw.get('primary_category', ''))
                    subcategory = LLMResponseParser.ensure_string(kw.get('subcategory', ''))
                    relevance_score = LLMResponseParser.validate_confidence(kw.get('relevance_score', 0.8))
                    
                    # Try to find matching taxonomy term
                    taxonomy_term = KeywordTaxonomy.query.filter(
                        KeywordTaxonomy.term == specific_term,
                        KeywordTaxonomy.primary_category == primary_category,
                        KeywordTaxonomy.subcategory == subcategory
                    ).first()
                    
                    # If no exact match, create a new taxonomy term
                    if not taxonomy_term:
                        # Check for similar terms first
                        similar_term = KeywordTaxonomy.query.filter(
                            KeywordTaxonomy.term.ilike(f"%{specific_term}%"),
                            KeywordTaxonomy.primary_category == primary_category
                        ).first()
                        
                        if similar_term:
                            # Use the similar term instead
                            taxonomy_term = similar_term
                            logger.info(f"Mapped to similar taxonomy term: {similar_term.term}")
                        else:
                            # Create new taxonomy term
                            taxonomy_term = KeywordTaxonomy(
                                term=specific_term,
                                primary_category=primary_category,
                                subcategory=subcategory,
                                specific_term=specific_term
                            )
                            db.session.add(taxonomy_term)
                            db.session.flush()  # Get the ID
                            logger.info(f"Created new taxonomy term: {specific_term}")
                            
                            # Add synonyms if provided
                            synonyms = kw.get('synonyms', [])
                            if synonyms and isinstance(synonyms, list):
                                for syn in synonyms:
                                    synonym = KeywordSynonym(
                                        taxonomy_id=taxonomy_term.id,
                                        synonym=LLMResponseParser.ensure_string(syn)
                                    )
                                    db.session.add(synonym)
                    
                    # Create document keyword association
                    doc_keyword = DocumentKeyword(
                        document_id=document_id,
                        taxonomy_id=taxonomy_term.id,
                        relevance_score=relevance_score
                    )
                    document_keywords.append(doc_keyword)
                    
                except Exception as e:
                    logger.error(f"Error processing individual keyword {kw}: {str(e)}")
                    continue
            
            logger.info(f"Successfully parsed {len(document_keywords)} document keywords")
            return document_keywords
            
        except Exception as e:
            logger.error(f"Error parsing hierarchical keywords: {str(e)}")
            raise
    
    @staticmethod
    def process_document_analysis(data: Dict[str, Any], document_id: int) -> bool:
        """
        Process the entire document analysis and store in database.
        This is a comprehensive method that handles all parts of the analysis.
        """
        try:
            # Process standard analysis fields using existing parser methods
            from app.services.llm_parser import LLMResponseParser
            parser = LLMResponseParser()
            
            # Basic LLM analysis
            llm_analysis_data = parser.parse_llm_analysis(data)
            from app.models.models import LLMAnalysis
            llm_analysis = LLMAnalysis(
                document_id=document_id,
                **llm_analysis_data
            )
            db.session.add(llm_analysis)
            db.session.flush()  # Get the ID
            
            # Process other standard components
            for component in ['extracted_text', 'design_elements', 'classification', 'entity_info', 'communication_focus']:
                try:
                    method_name = f'parse_{component}'
                    if hasattr(parser, method_name):
                        component_data = getattr(parser, method_name)(data)
                        
                        # Map component to model
                        component_to_model = {
                            'extracted_text': 'ExtractedText',
                            'design_elements': 'DesignElement',
                            'classification': 'Classification',
                            'entity_info': 'Entity',
                            'communication_focus': 'CommunicationFocus'
                        }
                        
                        if component in component_to_model:
                            from importlib import import_module
                            model_class = getattr(import_module('app.models.models'), component_to_model[component])
                            model_instance = model_class(document_id=document_id, **component_data)
                            db.session.add(model_instance)
                except Exception as e:
                    logger.error(f"Error processing {component}: {str(e)}")
            
            # Process hierarchical keywords - new functionality
            hierarchical_keywords = LLMResponseParser.parse_hierarchical_keywords(data, document_id)
            for keyword in hierarchical_keywords:
                db.session.add(keyword)
            
            # Commit all changes
            db.session.commit()
            logger.info(f"Successfully processed complete document analysis for document {document_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error processing document analysis: {str(e)}")
            db.session.rollback()
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
            
            for keyword in keywords[:10]:  # Limit to 10 keywords max
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
                'extraction_date': datetime.utcnow(),
                'page_number': 1  # Default page number
            }
            
            logger.info(f"Parsed extracted text with main message: {main_message[:50]}...")
            return result
            
        except Exception as e:
            logger.error(f"Error parsing extracted text: {str(e)}")
            raise

    @staticmethod
    def parse_design_elements(data: Dict[str, Any]) -> Dict[str, Any]:
        """Parse and validate design elements data"""
        try:
            design = data.get('design_elements', {})
            
            if not design:
                logger.warning("No design_elements found in LLM response")
                design = {}
            
            # Convert color_scheme list to JSON string if it's a list
            color_scheme = design.get('color_scheme', [])
            if isinstance(color_scheme, list):
                color_scheme = json.dumps(color_scheme)
            else:
                color_scheme = LLMResponseParser.ensure_string(color_scheme)
            
            # Convert visual_elements list to JSON string if it's a list
            visual_elements = design.get('visual_elements', [])
            if isinstance(visual_elements, list):
                visual_elements = json.dumps(visual_elements)
            else:
                visual_elements = LLMResponseParser.ensure_string(visual_elements)
            
            result = {
                'color_scheme': color_scheme,
                'theme': LLMResponseParser.ensure_string(design.get('theme', '')),
                'mail_piece_type': LLMResponseParser.ensure_string(design.get('mail_piece_type', '')),
                'geographic_location': LLMResponseParser.ensure_string(design.get('geographic_location', '')),
                'target_audience': LLMResponseParser.ensure_string(design.get('target_audience', '')),
                'campaign_name': LLMResponseParser.ensure_string(design.get('campaign_name', '')),
                'visual_elements': visual_elements,
                'confidence': int(LLMResponseParser.validate_confidence(
                    design.get('confidence', 0.0)
                ) * 100),
                'created_date': datetime.utcnow()
            }
            
            logger.info(f"Parsed design elements with theme: {result['theme']}")
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
            
            logger.info(f"Parsed classification with category: {result['category']}")
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
            
            logger.info(f"Parsed entity information with client: {result['client_name']}")
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
            if isinstance(secondary_issues, list):
                secondary_issues = json.dumps(secondary_issues)
            else:
                secondary_issues = LLMResponseParser.ensure_string(secondary_issues)
            
            result = {
                'primary_issue': LLMResponseParser.ensure_string(focus.get('primary_issue', '')),
                'secondary_issues': secondary_issues,
                'messaging_strategy': LLMResponseParser.ensure_string(focus.get('messaging_strategy', '')),
                'created_date': datetime.utcnow()
            }
            
            logger.info(f"Parsed communication focus with primary issue: {result['primary_issue']}")
            return result
            
        except Exception as e:
            logger.error(f"Error parsing communication focus: {str(e)}")
            raise
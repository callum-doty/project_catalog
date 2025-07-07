from typing import Dict, Any, List
import json
from datetime import datetime
import logging
import traceback
from src.catalog.models import KeywordTaxonomy, KeywordSynonym, LLMKeyword
from src.catalog import db
from src.catalog.services.taxonomy_service import TaxonomyService

logger = logging.getLogger(__name__)


class LLMResponseParser:

    @staticmethod
    def calculate_confidence(data: Dict[str, Any]) -> float:
        """Calculate a confidence score based on the presence of null values."""
        if not isinstance(data, dict):
            return 0.0

        total_fields = 0
        null_fields = 0

        def traverse(obj):
            nonlocal total_fields, null_fields
            if isinstance(obj, dict):
                for key, value in obj.items():
                    total_fields += 1
                    if value is None:
                        null_fields += 1
                    else:
                        traverse(value)
            elif isinstance(obj, list):
                for item in obj:
                    traverse(item)

        traverse(data)

        if total_fields == 0:
            return 0.0

        completeness = (total_fields - null_fields) / total_fields
        return round(completeness, 2)

    @staticmethod
    def ensure_string(value: Any, default: str = "") -> str:
        """Convert various types to string safely"""
        if value is None:
            return default

        if isinstance(value, list):
            return " ".join(str(item) for item in value)
        elif isinstance(value, dict):
            try:
                return json.dumps(value)
            except:
                return str(value)

        return str(value)

    @staticmethod
    def parse_llm_analysis(data: Dict[str, Any]) -> Dict[str, Any]:
        """Parse and validate basic LLM analysis data"""
        try:
            # Log the input data structure for debugging
            logger.info(
                f"Starting LLM analysis parsing with data keys: {list(data.keys())}"
            )

            # Check for null or empty data
            if not data:
                logger.warning("Empty data provided to parse_llm_analysis")
                raise ValueError("Empty data provided")

            # Extract document_analysis safely
            analysis = data.get("document_analysis", {})
            if not analysis:
                logger.warning("No document_analysis found in LLM response")
                analysis = {}

            # Log the analysis data structure
            logger.info(
                f"Analysis data type: {type(analysis)}, structure: {analysis if isinstance(analysis, dict) else 'non-dict'}"
            )

            # Convert to dict if the analysis is a string
            if isinstance(analysis, str):
                try:
                    analysis = json.loads(analysis)
                    logger.info("Successfully parsed string analysis as JSON")
                except json.JSONDecodeError as e:
                    logger.warning(
                        f"Could not parse document_analysis as JSON: {str(e)}"
                    )
                    analysis = {"summary": analysis}

            # Handle unexpected data structure
            if not isinstance(analysis, dict):
                logger.warning(
                    f"document_analysis is not a dictionary: {type(analysis)}"
                )
                analysis = {"summary": str(analysis)}

            # Extract fields with safe fallbacks
            summary = analysis.get("summary", "")
            campaign_type = analysis.get("campaign_type", "")
            election_year = analysis.get("election_year", "")
            document_tone = analysis.get("document_tone", "")

            # Log extractions for debugging
            logger.info(f"Extracted summary: {summary[:50]}...")

            # Safely convert and validate data
            result = {
                "summary_description": LLMResponseParser.ensure_string(summary),
                "content_analysis": json.dumps(analysis),
                "confidence_score": LLMResponseParser.calculate_confidence(analysis),
                "campaign_type": LLMResponseParser.ensure_string(campaign_type),
                "election_year": LLMResponseParser.ensure_string(election_year),
                "document_tone": LLMResponseParser.ensure_string(document_tone),
                "analysis_date": datetime.utcnow(),
                "model_version": "claude-3-opus-20240229",
            }

            logger.info(
                f"Successfully parsed LLM analysis with summary: {result['summary_description'][:50]}..."
            )
            return result

        except Exception as e:
            logger.error(f"Error parsing LLM analysis: {str(e)}")
            logger.error(f"Exception type: {type(e).__name__}")
            logger.error(f"Traceback: {traceback.format_exc()}")

            # Return minimal valid data
            return {
                "summary_description": f"Error parsing analysis: {str(e)}",
                "content_analysis": json.dumps({"error": str(e)}),
                "confidence_score": 0.0,
                "campaign_type": "",
                "election_year": "",
                "document_tone": "",
                "analysis_date": datetime.utcnow(),
                "model_version": "claude-3-opus-20240229",
            }

    @staticmethod
    def parse_classification(data: Dict[str, Any]) -> Dict[str, Any]:
        """Parse and validate classification data"""
        try:
            classification = data.get("classification", {})

            # Handle string or other non-dict values
            if not isinstance(classification, dict):
                logger.warning(
                    f"classification is not a dictionary: {type(classification)}"
                )
                if isinstance(classification, str):
                    try:
                        classification = json.loads(classification)
                    except:
                        classification = {"category": classification}
                else:
                    classification = {"category": str(classification)}

            if not classification:
                logger.warning("No classification found in LLM response")
                classification = {}

            result = {
                "category": LLMResponseParser.ensure_string(
                    classification.get("category", "")
                ),
                "classification_date": datetime.utcnow(),
            }

            logger.info(f"Parsed classification with category: {result['category']}")
            return result

        except Exception as e:
            logger.error(f"Error parsing classification: {str(e)}")
            logger.error(traceback.format_exc())

            # Return minimal valid data
            return {
                "category": "Error parsing classification",
                "confidence": 0,
                "classification_date": datetime.utcnow(),
            }

    @staticmethod
    def parse_design_elements(data: Dict[str, Any]) -> Dict[str, Any]:
        """Parse and validate design elements data"""
        try:
            design = data.get("design_elements", {})

            # Handle string or other non-dict values
            if not isinstance(design, dict):
                logger.warning(f"design_elements is not a dictionary: {type(design)}")
                if isinstance(design, str):
                    try:
                        design = json.loads(design)
                    except:
                        design = {"theme": design}
                else:
                    design = {"theme": str(design)}

            if not design:
                logger.warning("No design_elements found in LLM response")
                design = {}

            # Convert color_scheme list to JSON string if it's a list
            color_scheme = design.get("color_scheme", [])
            if isinstance(color_scheme, list):
                color_scheme = json.dumps(color_scheme)
            else:
                color_scheme = LLMResponseParser.ensure_string(color_scheme)

            # Convert visual_elements list to JSON string if it's a list
            visual_elements = design.get("visual_elements", [])
            if isinstance(visual_elements, list):
                visual_elements = json.dumps(visual_elements)
            else:
                visual_elements = LLMResponseParser.ensure_string(visual_elements)

            result = {
                "color_scheme": color_scheme,
                "theme": LLMResponseParser.ensure_string(design.get("theme", "")),
                "mail_piece_type": LLMResponseParser.ensure_string(
                    design.get("mail_piece_type", "")
                ),
                "geographic_location": LLMResponseParser.ensure_string(
                    design.get("geographic_location", "")
                ),
                "target_audience": LLMResponseParser.ensure_string(
                    design.get("target_audience", "")
                ),
                "campaign_name": LLMResponseParser.ensure_string(
                    design.get("campaign_name", "")
                ),
                "visual_elements": visual_elements,
                "created_date": datetime.utcnow(),
            }

            logger.info(f"Parsed design elements with theme: {result['theme']}")
            return result

        except Exception as e:
            logger.error(f"Error parsing design elements: {str(e)}")
            logger.error(traceback.format_exc())

            # Return minimal valid data
            return {
                "color_scheme": "[]",
                "theme": "Error parsing design elements",
                "mail_piece_type": "",
                "geographic_location": "",
                "target_audience": "",
                "campaign_name": "",
                "visual_elements": "[]",
                "confidence": 0,
                "created_date": datetime.utcnow(),
            }

    @staticmethod
    def parse_entity_info(data: Dict[str, Any]) -> Dict[str, Any]:
        """Parse and validate entity information"""
        try:
            # Log the input data structure for debugging
            logger.info(
                f"Starting entity info parsing with data keys: {list(data.keys())}"
            )
            logger.info(f"Raw data: {json.dumps(data, indent=2)}")

            # Check if data is already in the expected format (top-level keys)
            if all(
                key in data
                for key in [
                    "client_name",
                    "opponent_name",
                    "creation_date",
                    "survey_question",
                    "file_identifier",
                ]
            ):
                entities = data
                logger.info("Using top-level entity data")
            else:
                # Try to get entities from nested structure
                entities = data.get("entities", {})
                logger.info(f"Using nested entity data: {entities}")

            # Handle string or other non-dict values
            if not isinstance(entities, dict):
                logger.warning(f"entities is not a dictionary: {type(entities)}")
                if isinstance(entities, str):
                    try:
                        entities = json.loads(entities)
                        logger.info("Successfully parsed string entities as JSON")
                    except:
                        entities = {"client_name": entities}
                else:
                    entities = {"client_name": str(entities)}

            if not entities:
                logger.warning("No entities found in LLM response")
                entities = {}

            # Extract and validate each field
            client_name = LLMResponseParser.ensure_string(
                entities.get("client_name", "")
            )
            opponent_name = LLMResponseParser.ensure_string(
                entities.get("opponent_name", "")
            )
            creation_date = LLMResponseParser.ensure_string(
                entities.get("creation_date", "")
            )
            survey_question = LLMResponseParser.ensure_string(
                entities.get("survey_question", "")
            )
            file_identifier = LLMResponseParser.ensure_string(
                entities.get("file_identifier", "")
            )

            # Log extracted values
            logger.info(f"Extracted client_name: {client_name}")
            logger.info(f"Extracted opponent_name: {opponent_name}")
            logger.info(f"Extracted creation_date: {creation_date}")
            logger.info(f"Extracted survey_question: {survey_question}")
            logger.info(f"Extracted file_identifier: {file_identifier}")

            result = {
                "client_name": client_name,
                "opponent_name": opponent_name,
                "creation_date": creation_date,
                "survey_question": survey_question,
                "file_identifier": file_identifier,
                "created_date": datetime.utcnow(),
            }

            logger.info(
                f"Successfully parsed entity information with client: {result['client_name']}"
            )
            return result

        except Exception as e:
            logger.error(f"Error parsing entity information: {str(e)}")
            logger.error(traceback.format_exc())

            # Return minimal valid data
            return {
                "client_name": "Error parsing entity information",
                "opponent_name": "",
                "creation_date": "",
                "survey_question": "",
                "file_identifier": "",
                "created_date": datetime.utcnow(),
            }

    @staticmethod
    def parse_communication_focus(data: Dict[str, Any]) -> Dict[str, Any]:
        """Parse and validate communication focus data"""
        try:
            focus = data.get("communication_focus", {})

            # Handle string or other non-dict values
            if not isinstance(focus, dict):
                logger.warning(
                    f"communication_focus is not a dictionary: {type(focus)}"
                )
                if isinstance(focus, str):
                    try:
                        focus = json.loads(focus)
                    except:
                        focus = {"primary_issue": focus}
                else:
                    focus = {"primary_issue": str(focus)}

            if not focus:
                logger.warning("No communication_focus found in LLM response")
                focus = {}

            # Handle secondary_issues as a JSON array
            secondary_issues = focus.get("secondary_issues", [])
            if isinstance(secondary_issues, list):
                secondary_issues = json.dumps(secondary_issues)
            else:
                secondary_issues = LLMResponseParser.ensure_string(secondary_issues)

            # Handle messaging_strategy with validation
            messaging_strategy = focus.get("messaging_strategy", "")
            if messaging_strategy:
                # Normalize messaging strategy to lowercase
                messaging_strategy = messaging_strategy.lower()
                # Map to standard categories if needed
                strategy_mapping = {
                    "attack": "attack",
                    "positive": "positive",
                    "comparison": "comparison",
                    "contrast": "comparison",
                    "informational": "informational",
                    "educational": "informational",
                }
                messaging_strategy = strategy_mapping.get(
                    messaging_strategy, messaging_strategy
                )

            result = {
                "primary_issue": LLMResponseParser.ensure_string(
                    focus.get("primary_issue", "")
                ),
                "secondary_issues": secondary_issues,
                "messaging_strategy": LLMResponseParser.ensure_string(
                    messaging_strategy
                ),
                "created_date": datetime.utcnow(),
            }

            logger.info(
                f"Parsed communication focus with primary issue: {result['primary_issue']}"
            )
            return result

        except Exception as e:
            logger.error(f"Error parsing communication focus: {str(e)}")
            logger.error(traceback.format_exc())

            # Return minimal valid data
            return {
                "primary_issue": "Error parsing communication focus",
                "secondary_issues": "[]",
                "messaging_strategy": "",
                "created_date": datetime.utcnow(),
            }

    @staticmethod
    def parse_extracted_text(data: Dict[str, Any]) -> Dict[str, Any]:
        """Parse and validate extracted text data"""
        try:
            text_data = data.get("extracted_text", {})

            # Handle string or other non-dict values
            if not isinstance(text_data, dict):
                logger.warning(f"extracted_text is not a dictionary: {type(text_data)}")
                if isinstance(text_data, str):
                    try:
                        text_data = json.loads(text_data)
                    except:
                        text_data = {"text_content": text_data}
                else:
                    text_data = {"text_content": str(text_data)}

            if not text_data:
                logger.warning("No extracted_text found in LLM response")
                text_data = {}

            # Create a combined text content from main message and supporting text
            main_message = LLMResponseParser.ensure_string(
                text_data.get("main_message", "")
            )
            supporting_text = LLMResponseParser.ensure_string(
                text_data.get("supporting_text", "")
            )

            # Combine for backwards compatibility with existing field
            combined_text = f"{main_message}\n\n{supporting_text}"

            result = {
                "text_content": combined_text,
                "main_message": main_message,
                "supporting_text": supporting_text,
                "call_to_action": LLMResponseParser.ensure_string(
                    text_data.get("call_to_action", "")
                ),
                "extraction_date": datetime.utcnow(),
                "page_number": 1,  # Default page number
            }

            logger.info(
                f"Parsed extracted text with main message: {main_message[:50]}..."
            )
            return result

        except Exception as e:
            logger.error(f"Error parsing extracted text: {str(e)}")
            logger.error(traceback.format_exc())

            # Return minimal valid data
            return {
                "text_content": "Error parsing text",
                "main_message": "Error parsing text",
                "supporting_text": "",
                "call_to_action": "",
                "candidate_name": "",
                "opponent_name": "",
                "confidence": 0,
                "extraction_date": datetime.utcnow(),
                "page_number": 1,
            }

    @staticmethod
    def parse_keyword_mappings(
        data: Dict[str, Any], llm_analysis_id: int
    ) -> List[LLMKeyword]:
        """
        Parse keyword mappings from LLM response and create LLMKeyword objects.
        """
        try:
            keyword_mappings = data.get("keyword_mappings", [])
            if not keyword_mappings:
                logger.warning("No keyword_mappings found in LLM response")
                return []

            if isinstance(keyword_mappings, str):
                try:
                    keyword_mappings = json.loads(keyword_mappings)
                except json.JSONDecodeError:
                    logger.warning("Failed to parse keyword_mappings from string.")
                    return []

            document_keywords = []
            for mapping in keyword_mappings:
                if not isinstance(mapping, dict):
                    continue

                verbatim_term = mapping.get("verbatim_term")
                canonical_term = mapping.get("mapped_canonical_term")
                primary_category = mapping.get("mapped_primary_category")
                subcategory = mapping.get("mapped_subcategory")

                if not all(
                    [verbatim_term, canonical_term, primary_category, subcategory]
                ):
                    logger.warning(f"Skipping incomplete mapping: {mapping}")
                    continue

                # Find the canonical term in the database
                taxonomy_term = TaxonomyService.find_or_create_taxonomy_term(
                    term=canonical_term,
                    primary_category=primary_category,
                    subcategory=subcategory,
                    strict=True,  # Ensure we don't create new canonical terms
                )

                if taxonomy_term:
                    llm_keyword = LLMKeyword(
                        llm_analysis_id=llm_analysis_id,
                        taxonomy_id=taxonomy_term.id,
                        verbatim_term=verbatim_term,
                        relevance_score=0.9,  # Placeholder
                    )
                    document_keywords.append(llm_keyword)
                else:
                    logger.error(f"Canonical term not found for mapping: {mapping}")

            logger.info(
                f"Successfully parsed {len(document_keywords)} LLMKeywords from mappings."
            )
            return document_keywords

        except Exception as e:
            logger.error(f"Error parsing keyword mappings: {str(e)}")
            logger.error(traceback.format_exc())
            return []

    @staticmethod
    def parse_hierarchical_keywords(data: Dict[str, Any], document_id: int) -> List:
        """
        Parse hierarchical keywords from LLM response and create LLMKeyword objects.
        This method maps extracted keywords to taxonomy terms.
        """
        try:
            from sqlalchemy import func

            # Get hierarchical keywords from the response
            hierarchical_keywords = data.get("hierarchical_keywords", [])
            if not hierarchical_keywords:
                logger.warning("No hierarchical_keywords found in LLM response")
                return []

            if isinstance(hierarchical_keywords, str):
                try:
                    hierarchical_keywords = json.loads(hierarchical_keywords)
                except json.JSONDecodeError:
                    logger.warning("Failed to parse hierarchical_keywords from string.")
                    return []

            # We need to get the LLMAnalysis for this document first
            from src.catalog.models import LLMAnalysis

            llm_analysis = LLMAnalysis.query.filter_by(document_id=document_id).first()

            if not llm_analysis:
                logger.error(f"No LLMAnalysis found for document {document_id}")
                return []

            document_keywords = []

            for keyword_data in hierarchical_keywords:
                if not isinstance(keyword_data, dict):
                    continue

                keyword_text = keyword_data.get("keyword", "").strip()
                category = keyword_data.get("category", "").strip()
                relevance_score = keyword_data.get("relevance_score", 0.0)

                if not keyword_text:
                    continue

                # Try to find matching taxonomy term
                taxonomy_term = None

                # First, try exact match
                taxonomy_term = KeywordTaxonomy.query.filter(
                    func.lower(KeywordTaxonomy.term) == keyword_text.lower()
                ).first()

                # If no exact match, try partial match
                if not taxonomy_term:
                    taxonomy_term = KeywordTaxonomy.query.filter(
                        func.lower(KeywordTaxonomy.term).like(
                            f"%{keyword_text.lower()}%"
                        )
                    ).first()

                # If still no match, try synonyms
                if not taxonomy_term:
                    synonym_match = (
                        db.session.query(KeywordTaxonomy)
                        .join(
                            KeywordSynonym,
                            KeywordTaxonomy.id == KeywordSynonym.taxonomy_id,
                        )
                        .filter(
                            func.lower(KeywordSynonym.synonym) == keyword_text.lower()
                        )
                        .first()
                    )
                    if synonym_match:
                        taxonomy_term = synonym_match

                # Create LLMKeyword object
                if taxonomy_term:
                    llm_keyword = LLMKeyword(
                        llm_analysis_id=llm_analysis.id,
                        taxonomy_id=taxonomy_term.id,
                        keyword=keyword_text,
                        verbatim_term=keyword_text,  # For backward compatibility
                        category=category or taxonomy_term.primary_category,
                        relevance_score=(
                            float(relevance_score) if relevance_score else 0.0
                        ),
                    )
                    document_keywords.append(llm_keyword)
                    logger.info(
                        f"Mapped keyword '{keyword_text}' to taxonomy term '{taxonomy_term.term}'"
                    )
                else:
                    # Create keyword without taxonomy mapping
                    llm_keyword = LLMKeyword(
                        llm_analysis_id=llm_analysis.id,
                        taxonomy_id=None,
                        keyword=keyword_text,
                        verbatim_term=keyword_text,
                        category=category,
                        relevance_score=(
                            float(relevance_score) if relevance_score else 0.0
                        ),
                    )
                    document_keywords.append(llm_keyword)
                    logger.info(
                        f"No taxonomy match found for keyword '{keyword_text}', storing without mapping"
                    )

            logger.info(
                f"Successfully parsed {len(document_keywords)} hierarchical keywords for document {document_id}"
            )
            return document_keywords

        except Exception as e:
            logger.error(f"Error parsing hierarchical keywords: {str(e)}")
            logger.error(traceback.format_exc())
            return []

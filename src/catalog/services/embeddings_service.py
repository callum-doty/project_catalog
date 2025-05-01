import os
import httpx
import numpy as np
import json
import logging
from src.catalog import db, cache
from src.catalog.models import Document


logger = logging.getLogger(__name__)


class EmbeddingsService:
    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            logger.warning(
                "OPENAI_API_KEY environment variable is not set. Vector search will not work.")

        # Update to use the newer model
        # Updated to the newer OpenAI embeddings model
        self.model = "text-embedding-3-small"
        self.embedding_dim = 1536  # Dimensions for this model

    async def generate_embeddings(self, text):
        """Generate embeddings for text using OpenAI API"""
        if not self.api_key or not text:
            return None

        # Truncate text if too long (OpenAI has token limits)
        text = text[:8000]

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://api.openai.com/v1/embeddings",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "input": text,
                        "model": self.model,
                        "encoding_format": "float"  # Request float format
                    },
                    timeout=30.0
                )

                response.raise_for_status()
                data = response.json()

                # Extract the embedding
                embedding = data['data'][0]['embedding']
                return embedding

        except Exception as e:
            logger.error(f"Error generating embeddings: {str(e)}")
            return None

    async def generate_and_store_embeddings_for_document(self, document_id):
        """Generate and store embeddings for a document with enhanced context"""
        document = Document.query.get(document_id)
        if not document:
            logger.error(f"Document not found: {document_id}")
            return False

        # Build a richer context for embeddings
        text_to_embed = document.filename

        # Add analysis text if available
        if document.llm_analysis:
            llm_analysis = document.llm_analysis
            if llm_analysis.summary_description:
                text_to_embed += " " + llm_analysis.summary_description

        # Add extracted text if available
        if hasattr(document, 'extracted_text') and document.extracted_text:
            if document.extracted_text.text_content:
                text_to_embed += " " + document.extracted_text.text_content
            if document.extracted_text.main_message:
                text_to_embed += " " + document.extracted_text.main_message

        # Add keywords if available
        if document.llm_analysis and document.llm_analysis.keywords:
            keyword_text = " ".join(
                [kw.keyword for kw in document.llm_analysis.keywords if hasattr(kw, 'keyword')])
            text_to_embed += " " + keyword_text

        # Generate embeddings
        embeddings = await self.generate_embeddings(text_to_embed)
        if not embeddings:
            return False

        try:
            # Store embeddings in document
            document.embeddings = embeddings

            # If there's analysis, store embeddings there too
            if document.llm_analysis:
                analysis_text = document.llm_analysis.summary_description or ""
                if document.llm_analysis.content_analysis:
                    analysis_text += " " + document.llm_analysis.content_analysis

                analysis_embeddings = await self.generate_embeddings(analysis_text)
                if analysis_embeddings:
                    document.llm_analysis.embeddings = analysis_embeddings

            # Save to database
            db.session.commit()
            logger.info(
                f"Embeddings generated and stored for document {document_id}")
            return True
        except Exception as e:
            logger.error(f"Error storing embeddings: {str(e)}")
            db.session.rollback()
            return False

    @cache.memoize(timeout=300)
    async def generate_query_embeddings(self, query):
        """Generate embeddings for a search query with enhanced context based on taxonomy hierarchy"""
        # Master taxonomy-based term relationships
        taxonomy_terms = {
            # II. Policy Issues & Topics
            # A. Economy & Taxes
            "taxes": "taxes tax_cuts tax_increases tax_reform taxation revenue tariffs levies property_tax income_tax sales_tax corporate_tax tax_policy fiscal_policy",
            "inflation": "inflation rising_prices cost_of_living consumer_price_index CPI economic_pressure purchasing_power currency_devaluation monetary_policy",
            "jobs": "jobs employment unemployment workforce labor_market job_creation career opportunity hiring workers labor layoffs job_loss",
            "wages": "wages salary income compensation pay earnings minimum_wage living_wage fair_pay worker_compensation paychecks benefits",
            "budget": "budget spending fiscal_policy appropriations expenditures federal_budget state_budget municipal_budget allocation financial_plan",
            "deficit": "deficit debt national_debt federal_debt borrowing budget_deficit fiscal_hole revenue_shortfall government_borrowing",
            "small business": "small_business entrepreneur startup local_business small_enterprise family_business main_street job_creator business_owner",
            "trade": "trade imports exports tariffs global_trade international_commerce NAFTA trade_deficit trade_surplus protectionism free_trade",

            # B. Social Issues
            "abortion": "abortion reproductive_rights pro_choice pro_life roe_v_wade planned_parenthood right_to_life women's_healthcare",
            "lgbtq": "lgbtq gay_rights transgender same_sex_marriage gender_identity sexual_orientation equality non_discrimination",
            "marriage": "marriage same_sex_marriage traditional_marriage civil_union domestic_partnership marriage_equality",
            "religious freedom": "religious_freedom faith_based religion first_amendment religious_liberty religious_expression church_and_state",
            "family values": "family_values traditional_values moral_values conservative_values family_structure parental_rights",
            "marijuana": "marijuana cannabis legalization decriminalization medical_marijuana recreational_use drug_policy",

            # C. Healthcare
            "medicare": "medicare seniors healthcare_for_elderly retirement_benefits social_security health_insurance_for_seniors",
            "medicaid": "medicaid low_income_healthcare public_health_insurance safety_net healthcare_assistance",
            "affordable care act": "affordable_care_act obamacare aca healthcare_reform health_insurance_marketplace pre_existing_conditions",
            "prescription drugs": "prescription_drugs medication pharmaceutical drug_prices pharmacy medication_costs medicine",
            "mental health": "mental_health behavioral_health therapy counseling psychological psychiatric depression anxiety treatment",
            "healthcare costs": "healthcare_costs medical_expenses insurance_premiums deductibles copays out_of_pocket medical_bills",

            # D. Public Safety & Justice
            "crime": "crime criminal law_enforcement public_safety violence criminal_justice law_and_order crime_rates",
            "guns": "guns firearms gun_control second_amendment 2A gun_rights gun_safety gun_violence weapons",
            "police": "police law_enforcement officers cops sheriff police_reform public_safety community_policing blue_lives",
            "criminal justice reform": "criminal_justice_reform sentencing incarceration prison_reform rehabilitation recidivism prison mandatory_minimums",
            "border security": "border_security border_wall immigration_enforcement border_patrol border_crisis national_security southern_border",
            "immigration": "immigration immigrants migrant immigration_policy DACA citizenship naturalization deportation asylum refugee",

            # E. Environment & Energy
            "climate change": "climate_change global_warming carbon_emissions greenhouse_gas environment sustainability climate_crisis",
            "renewable energy": "renewable_energy solar wind clean_energy green_energy sustainable_energy alternative_energy clean_power",
            "fossil fuels": "fossil_fuels oil natural_gas coal petroleum traditional_energy carbon_based energy_independence fracking",
            "conservation": "conservation preservation wildlife natural_resources environmental_protection land_management parks forests",
            "pollution": "pollution emissions contamination air_quality water_pollution smog industrial_waste environmental_degradation",
            "water": "water clean_water drinking_water water_quality drought water_resources water_rights lakes rivers oceans",

            # F. Education
            "public schools": "public_schools k12 elementary_school middle_school high_school education system district_schools",
            "college affordability": "college_affordability tuition higher_education university college_costs education_expenses financial_aid",
            "student loans": "student_loans education_debt loan_forgiveness student_debt college_financing financial_aid",
            "school choice": "school_choice charter_schools vouchers private_schools educational_options alternative_education parental_choice",
            "teachers": "teachers educators faculty instructors school_staff teaching_profession teacher_pay teacher_benefits",
            "curriculum": "curriculum coursework education_standards common_core teaching_materials lesson_plans subject_matter education_content",

            # G. Government Reform
            "corruption": "corruption ethics transparency accountability integrity scandal government_reform drain_the_swamp",
            "election integrity": "election_integrity voting_security ballot_security election_security fraud_prevention secure_elections",
            "voting rights": "voting_rights voter_access ballot_access franchise democracy participation voter_suppression",
            "campaign finance": "campaign_finance political_donations fundraising dark_money super_pacs election_funding political_money",
            "term limits": "term_limits legislative_reform congressional_reform political_reform career_politicians government_reform",
            "lobbying": "lobbying special_interests influence influence_peddling industry_advocacy corporate_influence"
        }

        # III. Candidate & Entity Identifiers
        entity_terms = {
            "candidate": "candidate nominee contender politician officeholder office_seeker election_candidate",
            "democrat": "democratic democrat blue_party liberal progressive left left_leaning",
            "republican": "republican gop grand_old_party conservative right right_leaning red_party",
            "independent": "independent non_partisan non_affiliated third_party unaffiliated",
            "opposition": "opponent rival competition adversary challenger opposing_candidate competition",
            "endorsement": "endorsement support backing approval recommendation testimonial"
        }

        # IV. Communication Style & Format
        communication_terms = {
            "positive": "positive supportive uplifting optimistic hopeful promising favorable",
            "negative": "negative critical unfavorable disapproving hostile unflattering pessimistic",
            "contrast": "contrast comparison difference distinction distinguish comparing contrasting",
            "attack": "attack criticism hit_piece negative offensive accusatory aggressive hostile",
            "informational": "informational educational explanatory descriptive instructive informative",
            "mailer": "mailer mail_piece direct_mail political_mail campaign_literature flyer brochure"
        }

        # V-VII. Additional Categories
        additional_terms = {
            "election": "election vote ballot polling campaign contest race runoff primary general special",
            "campaign": "campaign election candidate race messaging strategy platform advertising outreach",
            "targeting": "targeting demographic audience segment voters constituents focus directed",
            "state level": "state statewide governor legislature statehouse assembly senate district",
            "local": "local municipal city county township borough mayor council alderman commissioner"
        }

        # Start with original query
        enhanced_query = query.lower()

        # Add taxonomy-specific context when query terms match
        added_terms = set()  # Track what we've added to avoid duplication

        # First check all our dictionaries for direct matches
        for category_dict in [taxonomy_terms, entity_terms, communication_terms, additional_terms]:
            for term, context in category_dict.items():
                if term.lower() in query.lower():
                    # Don't add duplicates
                    if term not in added_terms:
                        enhanced_query += " " + context
                        added_terms.add(term)

        # Check for compound terms across categories
        compound_terms = {
            "tax increase": "tax_increase revenue_raising fiscal_adjustment tax_hike levy_adjustment government_revenue tax_policy",
            "tax cut": "tax_reduction tax_relief fiscal_stimulus revenue_decrease taxpayer_benefit burden_reduction lower_taxes",
            "school board": "education_committee board_of_education school_trustees education_oversight school_district administration",
            "property tax": "real_estate_tax land_tax housing_tax municipal_revenue home_assessment local_tax county_tax",
            "minimum wage": "wage_floor lowest_legal_wage base_pay wage_standard labor_cost entry_level_pay hourly_minimum",
            "border wall": "border_barrier border_fence immigration_enforcement border_security border_protection southern_border",
            "election day": "voting_day polls ballot_casting election_date democracy_in_action civic_duty voting",
            "voter id": "voter_identification election_security ballot_integrity identity_verification voting_requirements",
            "campaign ad": "political_advertisement campaign_commercial electoral_messaging candidate_promotion political_messaging"
        }

        # Check for compound terms
        for compound, context in compound_terms.items():
            if compound.lower() in query.lower():
                enhanced_query += " " + context

        # Check for specific names of politicians
        name_indicators = [word for word in query.split() if word[0].isupper()]
        if name_indicators and any(term in query.lower() for term in ["vote", "election", "candidate", "campaign", "senator", "representative", "governor"]):
            enhanced_query += " politician candidate election campaign office position representative political"

        # Add temporal context if relevant
        temporal_terms = {
            "recent": "recent current latest present contemporary modern up_to_date",
            "past": "past previous former historical earlier prior old",
            "future": "future upcoming planned proposed prospective forthcoming",
            "election cycle": "election_cycle campaign_period voting_season electoral_period political_season"
        }

        for term, context in temporal_terms.items():
            if term in query.lower():
                enhanced_query += " " + context

        # Add geographic context if relevant
        geographic_terms = {
            "state": "state regional local district county municipal jurisdiction",
            "national": "national federal countrywide nationwide domestic",
            "local": "local community neighborhood district municipal county",
            "district": "district constituency precinct ward division electoral_area"
        }

        for term, context in geographic_terms.items():
            if term in query.lower():
                enhanced_query += " " + context

        # Add document type context
        document_types = {
            "mailer": "mailer direct_mail campaign_literature political_mail flyer brochure",
            "ad": "advertisement commercial spot announcement promotion marketing",
            "email": "email message correspondence communication electronic_mail",
            "social media": "social_media post tweet status_update social_network"
        }

        for doc_type, context in document_types.items():
            if doc_type in query.lower():
                enhanced_query += " " + context

        # Add sentiment context
        sentiment_terms = {
            "positive": "positive favorable supportive approving optimistic hopeful",
            "negative": "negative critical opposing disapproving pessimistic unfavorable",
            "neutral": "neutral objective impartial balanced unbiased factual"
        }

        for sentiment, context in sentiment_terms.items():
            if sentiment in query.lower():
                enhanced_query += " " + context

        # Add campaign strategy context
        strategy_terms = {
            "attack": "attack criticism negative opposition contrast comparison",
            "defense": "defense response rebuttal counterargument explanation justification",
            "promotion": "promotion positive support endorsement advocacy recommendation",
            "contrast": "contrast comparison difference distinction opposing alternative"
        }

        for strategy, context in strategy_terms.items():
            if strategy in query.lower():
                enhanced_query += " " + context

        # Log the enhancement for debugging
        if enhanced_query != query.lower():
            logger.info(
                f"Enhanced query '{query}' with taxonomy-specific terms")
            logger.debug(f"Original: '{query}' → Enhanced: '{enhanced_query}'")

        return await self.generate_embeddings(enhanced_query)

# app/services/taxonomy_service.py

import logging
import json
import csv
import os
from io import StringIO
from app.models.keyword_models import KeywordTaxonomy, KeywordSynonym
from app.extensions import db
from sqlalchemy.exc import SQLAlchemyError
from flask import current_app

logger = logging.getLogger(__name__)

class TaxonomyService:
    """Service for managing keyword taxonomy"""
    
    @staticmethod
    def initialize_taxonomy_from_file(file_path):
        """Initialize taxonomy from a structured CSV file"""
        try:
            if not os.path.exists(file_path):
                logger.error(f"Taxonomy file not found: {file_path}")
                return False, "Taxonomy file not found"
            
            with open(file_path, 'r') as f:
                reader = csv.DictReader(f)
                rows = list(reader)
                
            counter = {'created': 0, 'errors': 0}
            
            # First pass: Create all primary terms
            primary_terms = {}
            for row in rows:
                # Check required fields
                if not row.get('primary_category') or not row.get('term'):
                    counter['errors'] += 1
                    continue
                    
                try:
                    # Create the term
                    term = KeywordTaxonomy(
                        term=row['term'],
                        primary_category=row['primary_category'],
                        subcategory=row.get('subcategory', ''),
                        specific_term=row.get('specific_term', row['term']),
                        description=row.get('description', '')
                    )
                    db.session.add(term)
                    db.session.flush()
                    
                    # Store for second pass to establish relationships
                    primary_terms[row['term']] = term
                    
                    # Handle synonyms if provided
                    if row.get('synonyms'):
                        synonyms = [s.strip() for s in row['synonyms'].split(',') if s.strip()]
                        for syn in synonyms:
                            synonym = KeywordSynonym(
                                taxonomy_id=term.id,
                                synonym=syn
                            )
                            db.session.add(synonym)
                    
                    counter['created'] += 1
                except Exception as e:
                    logger.error(f"Error creating taxonomy term {row.get('term')}: {str(e)}")
                    counter['errors'] += 1
                    continue
            
            # Second pass: Establish parent/child relationships
            for row in rows:
                if row.get('parent_term') and row.get('term'):
                    try:
                        child_term = primary_terms.get(row['term'])
                        parent_term = primary_terms.get(row['parent_term'])
                        
                        if child_term and parent_term:
                            child_term.parent_id = parent_term.id
                    except Exception as e:
                        logger.error(f"Error establishing relationship for {row.get('term')}: {str(e)}")
            
            # Commit all changes
            db.session.commit()
            logger.info(f"Taxonomy initialization complete: {counter['created']} terms created, {counter['errors']} errors")
            return True, f"Successfully created {counter['created']} taxonomy terms"
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Taxonomy initialization failed: {str(e)}")
            return False, f"Taxonomy initialization failed: {str(e)}"
    
    @staticmethod
    def export_taxonomy_to_csv():
        """Export the entire taxonomy to CSV format"""
        try:
            # Query all taxonomy terms
            terms = KeywordTaxonomy.query.all()
            
            if not terms:
                return False, "No taxonomy terms found to export"
                
            # Create CSV in memory
            output = StringIO()
            writer = csv.writer(output)
            
            # Write header
            writer.writerow([
                'id', 'term', 'primary_category', 'subcategory', 'specific_term',
                'parent_id', 'description', 'synonyms'
            ])
            
            # Write data rows
            for term in terms:
                # Get synonyms as comma-separated string
                synonyms = ', '.join([s.synonym for s in term.synonyms]) if term.synonyms else ''
                
                writer.writerow([
                    term.id,
                    term.term,
                    term.primary_category,
                    term.subcategory or '',
                    term.specific_term or '',
                    term.parent_id or '',
                    term.description or '',
                    synonyms
                ])
            
            # Get CSV as string
            csv_data = output.getvalue()
            output.close()
            
            return True, csv_data
        
        except Exception as e:
            logger.error(f"Error exporting taxonomy: {str(e)}")
            return False, f"Export failed: {str(e)}"
    
    @staticmethod
    def get_taxonomy_stats():
        """Get statistics about the taxonomy"""
        try:
            stats = {
                'total_terms': KeywordTaxonomy.query.count(),
                'primary_categories': {},
                'terms_with_synonyms': db.session.query(KeywordTaxonomy.id).join(KeywordSynonym).distinct().count(),
                'total_synonyms': KeywordSynonym.query.count(),
                'hierarchical_terms': KeywordTaxonomy.query.filter(KeywordTaxonomy.parent_id.isnot(None)).count()
            }
            
            # Get counts by primary category
            category_counts = db.session.query(
                KeywordTaxonomy.primary_category,
                db.func.count(KeywordTaxonomy.id)
            ).group_by(KeywordTaxonomy.primary_category).all()
            
            for category, count in category_counts:
                stats['primary_categories'][category] = count
            
            return stats
        except Exception as e:
            logger.error(f"Error getting taxonomy stats: {str(e)}")
            return {'error': str(e)}
    
    @staticmethod
    def find_or_create_taxonomy_term(term, primary_category, subcategory=None, synonyms=None):
        """Find an existing taxonomy term or create a new one"""
        try:
            # Normalize inputs
            term = term.strip()
            primary_category = primary_category.strip()
            subcategory = subcategory.strip() if subcategory else None
            
            # Check for existing term
            existing_term = KeywordTaxonomy.query.filter(
                KeywordTaxonomy.term == term,
                KeywordTaxonomy.primary_category == primary_category
            )
            
            if subcategory:
                existing_term = existing_term.filter(KeywordTaxonomy.subcategory == subcategory)
                
            existing_term = existing_term.first()
            
            if existing_term:
                # Term exists, add any new synonyms
                if synonyms:
                    # Get existing synonyms
                    existing_synonyms = [s.synonym for s in existing_term.synonyms]
                    
                    # Add new synonyms
                    for syn in synonyms:
                        if syn and syn not in existing_synonyms:
                            synonym = KeywordSynonym(
                                taxonomy_id=existing_term.id,
                                synonym=syn
                            )
                            db.session.add(synonym)
                    
                    db.session.commit()
                
                return existing_term
            
            # Create new term
            new_term = KeywordTaxonomy(
                term=term,
                primary_category=primary_category,
                subcategory=subcategory,
                specific_term=term
            )
            db.session.add(new_term)
            db.session.flush()  # Get the ID
            
            # Add synonyms if provided
            if synonyms:
                for syn in synonyms:
                    if syn:
                        synonym = KeywordSynonym(
                            taxonomy_id=new_term.id,
                            synonym=syn
                        )
                        db.session.add(synonym)
            
            db.session.commit()
            logger.info(f"Created new taxonomy term: {term} ({primary_category})")
            return new_term
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error finding/creating taxonomy term: {str(e)}")
            raise

# Sample initial taxonomy structure for Policy Issues
POLICY_ISSUES_TAXONOMY = [
    {"primary_category": "Policy Issues & Topics", "subcategory": "Economy & Taxes", "term": "Taxes", "synonyms": "tax cuts, tax reform, tax increases, taxation"},
    {"primary_category": "Policy Issues & Topics", "subcategory": "Economy & Taxes", "term": "Inflation", "synonyms": "price increases, cost of living, rising prices"},
    {"primary_category": "Policy Issues & Topics", "subcategory": "Economy & Taxes", "term": "Jobs", "synonyms": "employment, unemployment, job creation, workforce"},
    
    {"primary_category": "Policy Issues & Topics", "subcategory": "Social Issues", "term": "Abortion", "synonyms": "reproductive rights, pro-life, pro-choice, Roe v Wade"},
    {"primary_category": "Policy Issues & Topics", "subcategory": "Social Issues", "term": "LGBTQ+ Rights", "synonyms": "gay rights, transgender, same-sex marriage"},
    
    {"primary_category": "Policy Issues & Topics", "subcategory": "Healthcare", "term": "Medicare", "synonyms": "Medicare for All, senior healthcare"},
    {"primary_category": "Policy Issues & Topics", "subcategory": "Healthcare", "term": "Affordable Care Act", "synonyms": "Obamacare, ACA, healthcare reform"},
    
    {"primary_category": "Policy Issues & Topics", "subcategory": "Public Safety", "term": "Guns", "synonyms": "gun control, second amendment, firearms, gun violence"},
    {"primary_category": "Policy Issues & Topics", "subcategory": "Public Safety", "term": "Crime", "synonyms": "criminal justice, law and order, police"},
    
    {"primary_category": "Policy Issues & Topics", "subcategory": "Environment", "term": "Climate Change", "synonyms": "global warming, carbon emissions, paris agreement"},
    
    {"primary_category": "Policy Issues & Topics", "subcategory": "Education", "term": "Public Schools", "synonyms": "education funding, teachers, school choice"},
    
    {"primary_category": "Policy Issues & Topics", "subcategory": "Government Reform", "term": "Corruption", "synonyms": "drain the swamp, ethics, political corruption"},
]
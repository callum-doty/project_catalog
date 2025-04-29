

from src.catalog.extensions import db
from src.catalog.models import KeywordTaxonomy, KeywordSynonym
from src.catalog import create_app
import os
import sys
import logging
import datetime

# Add the parent directory to the path so we can import app modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# Initialize base taxonomy data
BASE_TAXONOMY = {
    "Policy Issues & Topics": {
        "Economy & Taxes": ["Taxes", "Inflation", "Jobs", "Wages", "Budget", "Deficit", "Trade"],
        "Social Issues": ["Abortion", "LGBTQ+ Rights", "Marriage Equality", "Religious Freedom", "Family Values"],
        "Healthcare": ["Medicare", "Medicaid", "Affordable Care Act", "Prescription Drugs", "Mental Health"],
        "Public Safety": ["Crime", "Guns", "Police", "Immigration", "Border Security"],
        "Environment": ["Climate Change", "Renewable Energy", "Fossil Fuels", "Conservation"],
        "Education": ["Public Schools", "College Affordability", "Student Loans", "Teachers"],
        "Government Reform": ["Corruption", "Election Integrity", "Voting Rights", "Term Limits"]
    },
    "Candidate & Entity": {
        "Candidate Elements": ["Name", "Party", "Previous Office", "Current Office", "Biography"],
        "Political Parties": ["Democratic", "Republican", "Independent", "Progressive", "Conservative"],
        "Opposition Elements": ["Opponent Name", "Criticism", "Contrast Points"],
        "External Endorsements": ["Organizations", "Leaders", "Unions", "Celebrities"]
    },
    "Communication Style": {
        "Message Tone": ["Positive", "Negative", "Contrast", "Attack", "Informational"],
        "Mail Piece Types": ["Postcard", "Mailer", "Brochure", "Letter", "Push Card"],
        "Message Focus": ["Introduction", "Issue-Based", "Biography", "Endorsement", "GOTV"],
        "Visual Design": ["Color Scheme", "Photography", "Graphics", "Typography", "Layout"]
    },
    "Geographic & Demographic": {
        "Geographic Level": ["National", "Statewide", "Congressional", "County", "City"],
        "Target Audience": ["Age Group", "Gender", "Race/Ethnicity", "Education", "Income"]
    },
    "Campaign Context": {
        "Election Type": ["General", "Primary", "Special", "Runoff", "Recall"],
        "Election Year": ["2024", "2022", "2020"],
        "Office Sought": ["Presidential", "Senate", "House", "Governor", "State", "Local"],
        "Campaign Phase": ["Early Campaign", "Late Campaign", "GOTV Period"]
    }
}

# Synonym mappings for common terms
SYNONYM_MAPPINGS = {
    "Taxes": ["tax cuts", "tax reform", "tax increases", "taxation"],
    "Inflation": ["price increases", "cost of living", "rising prices"],
    "Jobs": ["employment", "unemployment", "job creation", "workforce"],
    "Abortion": ["reproductive rights", "pro-life", "pro-choice", "Roe v Wade"],
    "LGBTQ+ Rights": ["gay rights", "transgender", "same-sex marriage"],
    "Medicare": ["Medicare for All", "senior healthcare"],
    "Affordable Care Act": ["Obamacare", "ACA", "healthcare reform"],
    "Guns": ["gun control", "second amendment", "firearms", "gun violence"],
    "Crime": ["criminal justice", "law and order", "police", "public safety"],
    "Climate Change": ["global warming", "carbon emissions", "paris agreement"],
    "Corruption": ["drain the swamp", "ethics", "political corruption"],
    "Democratic": ["Democrat", "DNC", "blue"],
    "Republican": ["GOP", "RNC", "red"],
}


def initialize_taxonomy():
    """Initialize the taxonomy directly from the dictionary data"""
    app = create_app()
    with app.app_context():
        try:
            # Check if we already have taxonomy terms
            existing_count = KeywordTaxonomy.query.count()
            if existing_count > 0:
                print(
                    f"Found {existing_count} existing taxonomy terms. Skipping initialization.")
                return

            created_count = 0
            for primary_category, subcategories in BASE_TAXONOMY.items():
                for subcategory, terms in subcategories.items():
                    for term in terms:
                        try:
                            # Create the taxonomy term
                            taxonomy_term = KeywordTaxonomy(
                                term=term,
                                primary_category=primary_category,
                                subcategory=subcategory,
                                specific_term=term,
                                created_date=datetime.utcnow()
                            )
                            db.session.add(taxonomy_term)
                            db.session.flush()  # Get the ID

                            # Add synonyms if available
                            synonyms = SYNONYM_MAPPINGS.get(term, [])
                            for synonym in synonyms:
                                synonym_obj = KeywordSynonym(
                                    taxonomy_id=taxonomy_term.id,
                                    synonym=synonym
                                )
                                db.session.add(synonym_obj)

                            created_count += 1

                            # Commit in batches to avoid large transactions
                            if created_count % 20 == 0:
                                db.session.commit()
                                print(
                                    f"Created {created_count} taxonomy terms so far...")

                        except Exception as e:
                            print(
                                f"Error creating taxonomy term '{term}': {str(e)}")
                            continue

            # Final commit for any remaining terms
            db.session.commit()
            print(f"Successfully created {created_count} taxonomy terms.")

        except Exception as e:
            db.session.rollback()
            print(f"Error initializing taxonomy: {str(e)}")


if __name__ == "__main__":
    initialize_taxonomy()

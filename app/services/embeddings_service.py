# app/services/embeddings_service.py
import os
import httpx
import numpy as np
import json
import logging
from app.extensions import db, cache
from app.models.models import Document, LLMAnalysis

logger = logging.getLogger(__name__)

# app/services/embeddings_service.py
import os
import httpx
import numpy as np
import json
import logging
from app.extensions import db, cache
from app.models.models import Document, LLMAnalysis

logger = logging.getLogger(__name__)

class EmbeddingsService:
    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            logger.warning("OPENAI_API_KEY environment variable is not set. Vector search will not work.")
        
        # Update to use the newer model
        self.model = "text-embedding-3-small"  # Updated to the newer OpenAI embeddings model
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
            keyword_text = " ".join([kw.keyword for kw in document.llm_analysis.keywords if hasattr(kw, 'keyword')])
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
            logger.info(f"Embeddings generated and stored for document {document_id}")
            return True
        except Exception as e:
            logger.error(f"Error storing embeddings: {str(e)}")
            db.session.rollback()
            return False
    
    @cache.memoize(timeout=300)
    async def generate_query_embeddings(self, query):
        """Generate embeddings for a search query with enhanced context"""
        # Add common related terms for financial queries
        financial_terms = {
            "money": "money finances financial currency cash funds fees taxes payments income revenue",
            "tax": "tax taxes taxation tariff levy duty revenue income",
            "fee": "fee fees charge cost expense payment price toll",
            "sale": "sale sales revenue income proceeds profit transaction",
        }
        
        enhanced_query = query
        for term, context in financial_terms.items():
            if term.lower() in query.lower():
                enhanced_query += " " + context
                
        return await self.generate_embeddings(enhanced_query)

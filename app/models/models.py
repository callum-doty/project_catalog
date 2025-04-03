from app.extensions import db
from datetime import datetime


class BatchJob(db.Model):
   __tablename__ = 'batch_jobs'
   id = db.Column(db.Integer, primary_key=True)
   job_name = db.Column(db.Text, nullable=False)
   start_time = db.Column(db.DateTime(timezone=True), nullable=False)
   end_time = db.Column(db.DateTime(timezone=True))
   file_size = db.Column(db.BigInteger, nullable=False)
   status = db.Column(db.Text, nullable=False)
   total_documents = db.Column(db.Integer, nullable=False)
   processed_documents = db.Column(db.Integer)


class Document(db.Model):
   __tablename__ = 'documents'
   id = db.Column(db.Integer, primary_key=True)
   filename = db.Column(db.Text, nullable=False)
   upload_date = db.Column(db.DateTime(timezone=True), nullable=False)
   processing_time = db.Column(db.Float, nullable=True)
   file_size = db.Column(db.BigInteger, nullable=False)
   page_count = db.Column(db.Integer, nullable=False)
   status = db.Column(db.Text, nullable=False)
   batch_jobs_id = db.Column(db.Integer, db.ForeignKey('batch_jobs.id'))


   # Relationships
   llm_analysis = db.relationship('LLMAnalysis', backref='document', lazy='joined', uselist=False)
   extracted_text = db.relationship('ExtractedText', backref='document', lazy='joined', uselist=False)
   design_elements = db.relationship('DesignElement', backref='document', lazy='joined', uselist=False)
   classification = db.relationship('Classification', backref='document', lazy='joined', uselist=False)
   entity = db.relationship('Entity', backref='document', lazy='joined', uselist=False)
   communication_focus = db.relationship('CommunicationFocus', backref='document', lazy='joined', uselist=False)


class Entity(db.Model):
   """Stores entity information from the document"""
   __tablename__ = 'entities'
   id = db.Column(db.Integer, primary_key=True)
   document_id = db.Column(db.Integer, db.ForeignKey('documents.id'))
   client_name = db.Column(db.Text)
   opponent_name = db.Column(db.Text)
   creation_date = db.Column(db.Text)
   survey_question = db.Column(db.Text)
   file_identifier = db.Column(db.Text)
   created_date = db.Column(db.DateTime(timezone=True), default=datetime.utcnow)


class CommunicationFocus(db.Model):
   """Stores the communication focus and messaging strategy"""
   __tablename__ = 'communication_focus'
   id = db.Column(db.Integer, primary_key=True)
   document_id = db.Column(db.Integer, db.ForeignKey('documents.id'))
   primary_issue = db.Column(db.Text)
   secondary_issues = db.Column(db.Text)  # JSON array stored as text
   messaging_strategy = db.Column(db.Text)
   created_date = db.Column(db.DateTime(timezone=True), default=datetime.utcnow)


class DesignElement(db.Model):
   __tablename__ = 'design_elements'
   id = db.Column(db.Integer, primary_key=True)
   document_id = db.Column(db.Integer, db.ForeignKey('documents.id'))
   color_scheme = db.Column(db.Text)
   theme = db.Column(db.Text)
   mail_piece_type = db.Column(db.Text)
   geographic_location = db.Column(db.Text)
   target_audience = db.Column(db.Text)
   campaign_name = db.Column(db.Text)
   visual_elements = db.Column(db.Text)  # JSON array stored as text
   confidence = db.Column(db.BigInteger)
   created_date = db.Column(db.DateTime(timezone=True))


class LLMAnalysis(db.Model):
   __tablename__ = 'llm_analysis'
   id = db.Column(db.Integer, primary_key=True)
   document_id = db.Column(db.Integer, db.ForeignKey('documents.id'))
   summary_description = db.Column(db.Text)
   visual_analysis = db.Column(db.Text)
   content_analysis = db.Column(db.Text)
   campaign_type = db.Column(db.Text)
   election_year = db.Column(db.Text)
   document_tone = db.Column(db.Text)
   confidence_score = db.Column(db.Float)
   analysis_date = db.Column(db.DateTime(timezone=True))
   model_version = db.Column(db.Text)
  
   # Relationship with keywords
   keywords = db.relationship('LLMKeyword', backref='analysis', lazy='joined')


class Client(db.Model):
   __tablename__ = 'clients'
   id = db.Column(db.Integer, primary_key=True)
   client_name = db.Column(db.Text)
   campaign_name = db.Column(db.Text)
   created_date = db.Column(db.DateTime(timezone=True))
   notes = db.Column(db.Text)
   document_id = db.Column(db.Integer, db.ForeignKey('documents.id'))


class LLMKeyword(db.Model):
   __tablename__ = 'llm_keywords'
   id = db.Column(db.Integer, primary_key=True)
   llm_analysis_id = db.Column(db.Integer, db.ForeignKey('llm_analysis.id'))
   keyword = db.Column(db.Text)
   category = db.Column(db.Text)
   relevance_score = db.Column(db.BigInteger)


class Classification(db.Model):
   __tablename__ = 'classifications'
   id = db.Column(db.Integer, primary_key=True)
   document_id = db.Column(db.Integer, db.ForeignKey('documents.id'))
   category = db.Column(db.Text)
   confidence = db.Column(db.BigInteger)
   classification_date = db.Column(db.DateTime(timezone=True))


class ExtractedText(db.Model):
   __tablename__ = 'extracted_text'
   id = db.Column(db.Integer, primary_key=True)
   document_id = db.Column(db.Integer, db.ForeignKey('documents.id'))
   page_number = db.Column(db.Integer)
   text_content = db.Column(db.Text)
   main_message = db.Column(db.Text)
   supporting_text = db.Column(db.Text)
   call_to_action = db.Column(db.Text)
   candidate_name = db.Column(db.Text)
   opponent_name = db.Column(db.Text)
   confidence = db.Column(db.BigInteger)
   extraction_date = db.Column(db.DateTime(timezone=True))


class DropboxSync(db.Model):
   __tablename__ = 'dropbox_syncs'
  
   id = db.Column(db.Integer, primary_key=True)
   document_id = db.Column(db.Integer, db.ForeignKey('documents.id'))
   dropbox_file_id = db.Column(db.String(255), unique=True)
   dropbox_path = db.Column(db.String(512))
   sync_date = db.Column(db.DateTime(timezone=True))
   status = db.Column(db.String(50), default='SYNCED')



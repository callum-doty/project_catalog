-- Create tables in the right order
CREATE TABLE IF NOT EXISTS batch_jobs (
  id SERIAL PRIMARY KEY,
  job_name TEXT NOT NULL,
  start_time TIMESTAMP WITH TIME ZONE NOT NULL,
  end_time TIMESTAMP WITH TIME ZONE,
  file_size BIGINT NOT NULL,
  status TEXT NOT NULL,
  total_documents INTEGER NOT NULL,
  processed_documents INTEGER
);

CREATE TABLE IF NOT EXISTS documents (
  id SERIAL PRIMARY KEY,
  filename TEXT NOT NULL,
  upload_date TIMESTAMP WITH TIME ZONE NOT NULL,
  file_size BIGINT NOT NULL,
  page_count INTEGER NOT NULL,
  status TEXT NOT NULL,
  batch_jobs_id INTEGER,
  processing_time FLOAT,
  search_vector TSVECTOR,
  FOREIGN KEY(batch_jobs_id) REFERENCES batch_jobs (id)
);

CREATE TABLE IF NOT EXISTS keyword_taxonomy (
  id SERIAL PRIMARY KEY,
  term TEXT NOT NULL,
  primary_category TEXT NOT NULL,
  subcategory TEXT,
  specific_term TEXT,
  description TEXT,
  created_date TIMESTAMP WITH TIME ZONE,
  parent_id INTEGER,
  FOREIGN KEY(parent_id) REFERENCES keyword_taxonomy (id)
);

-- Document scorecards table
CREATE TABLE IF NOT EXISTS document_scorecards (
  id SERIAL PRIMARY KEY,
  document_id INTEGER NOT NULL,
  metadata_score INTEGER,
  text_extraction_score INTEGER,
  classification_score INTEGER,
  entity_score INTEGER,
  design_score INTEGER,
  keyword_score INTEGER,
  communication_score INTEGER,
  total_score INTEGER,
  requires_review BOOLEAN,
  review_reason TEXT,
  batch1_success BOOLEAN,
  batch2_success BOOLEAN,
  batch3_success BOOLEAN,
  metadata_flags TEXT,
  text_flags TEXT,
  classification_flags TEXT,
  entity_flags TEXT,
  design_flags TEXT,
  keyword_flags TEXT,
  communication_flags TEXT,
  reviewed BOOLEAN,
  review_date TIMESTAMP WITH TIME ZONE,
  reviewer_notes TEXT,
  corrections_made TEXT,
  created_date TIMESTAMP WITH TIME ZONE,
  updated_date TIMESTAMP WITH TIME ZONE,
  FOREIGN KEY(document_id) REFERENCES documents (id)
);

-- Create other essential tables based on your schema
CREATE TABLE IF NOT EXISTS llm_analysis (
  id SERIAL PRIMARY KEY,
  document_id INTEGER NOT NULL,
  summary_description TEXT,
  visual_analysis TEXT,
  content_analysis TEXT,
  confidence_score FLOAT,
  analysis_date TIMESTAMP WITH TIME ZONE,
  model_version TEXT,
  campaign_type TEXT,
  election_year TEXT,
  document_tone TEXT,
  search_vector TSVECTOR,
  FOREIGN KEY(document_id) REFERENCES documents (id)
);

CREATE TABLE IF NOT EXISTS llm_keywords (
  id SERIAL PRIMARY KEY,
  llm_analysis_id INTEGER NOT NULL,
  keyword TEXT,
  category TEXT,
  relevance_score BIGINT,
  taxonomy_id INTEGER,
  FOREIGN KEY(llm_analysis_id) REFERENCES llm_analysis (id),
  FOREIGN KEY(taxonomy_id) REFERENCES keyword_taxonomy (id)
);

CREATE TABLE IF NOT EXISTS extracted_text (
  id SERIAL PRIMARY KEY,
  document_id INTEGER NOT NULL,
  page_number INTEGER,
  text_content TEXT,
  main_message TEXT,
  supporting_text TEXT,
  call_to_action TEXT,
  candidate_name TEXT,
  opponent_name TEXT,
  confidence BIGINT,
  extraction_date TIMESTAMP WITH TIME ZONE,
  search_vector TSVECTOR,
  FOREIGN KEY(document_id) REFERENCES documents (id)
);

-- Add this to mark the migration as complete
CREATE TABLE IF NOT EXISTS alembic_version (
    version_num VARCHAR(32) NOT NULL
);

-- Clear any existing version
DELETE FROM alembic_version;

-- Set the migration version to your latest
INSERT INTO alembic_version (version_num) VALUES ('38338ee4e36e');
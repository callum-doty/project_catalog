--
-- PostgreSQL database dump
--

-- Dumped from database version 14.17 (Debian 14.17-1.pgdg120+1)
-- Dumped by pg_dump version 14.17 (Debian 14.17-1.pgdg120+1)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: vector; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA public;


--
-- Name: EXTENSION vector; Type: COMMENT; Schema: -; Owner: 
--

COMMENT ON EXTENSION vector IS 'vector data type and ivfflat access method';


--
-- Name: documents_search_vector_update(); Type: FUNCTION; Schema: public; Owner: custom_user
--

CREATE FUNCTION public.documents_search_vector_update() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
    BEGIN
        NEW.search_vector = to_tsvector('english', COALESCE(NEW.filename, ''));
        RETURN NEW;
    END
    $$;


ALTER FUNCTION public.documents_search_vector_update() OWNER TO custom_user;

--
-- Name: extracted_text_search_vector_update(); Type: FUNCTION; Schema: public; Owner: custom_user
--

CREATE FUNCTION public.extracted_text_search_vector_update() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
    BEGIN
        NEW.search_vector = to_tsvector('english', 
            COALESCE(NEW.text_content, '') || ' ' || 
            COALESCE(NEW.main_message, '') || ' ' || 
            COALESCE(NEW.supporting_text, '') || ' ' || 
            COALESCE(NEW.call_to_action, ''));
        RETURN NEW;
    END
    $$;


ALTER FUNCTION public.extracted_text_search_vector_update() OWNER TO custom_user;

--
-- Name: llm_analysis_search_vector_update(); Type: FUNCTION; Schema: public; Owner: custom_user
--

CREATE FUNCTION public.llm_analysis_search_vector_update() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
    BEGIN
        NEW.search_vector = to_tsvector('english', 
            COALESCE(NEW.summary_description, '') || ' ' || 
            COALESCE(NEW.campaign_type, '') || ' ' || 
            COALESCE(NEW.election_year, '') || ' ' || 
            COALESCE(NEW.document_tone, ''));
        RETURN NEW;
    END
    $$;


ALTER FUNCTION public.llm_analysis_search_vector_update() OWNER TO custom_user;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: batch_jobs; Type: TABLE; Schema: public; Owner: custom_user
--

CREATE TABLE public.batch_jobs (
    id integer NOT NULL,
    job_name text NOT NULL,
    start_time timestamp with time zone NOT NULL,
    end_time timestamp with time zone,
    file_size bigint NOT NULL,
    status text NOT NULL,
    total_documents integer NOT NULL,
    processed_documents integer
);


ALTER TABLE public.batch_jobs OWNER TO custom_user;

--
-- Name: batch_jobs_id_seq; Type: SEQUENCE; Schema: public; Owner: custom_user
--

CREATE SEQUENCE public.batch_jobs_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.batch_jobs_id_seq OWNER TO custom_user;

--
-- Name: batch_jobs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: custom_user
--

ALTER SEQUENCE public.batch_jobs_id_seq OWNED BY public.batch_jobs.id;


--
-- Name: classifications; Type: TABLE; Schema: public; Owner: custom_user
--

CREATE TABLE public.classifications (
    id integer NOT NULL,
    document_id integer,
    category text,
    confidence bigint,
    classification_date timestamp with time zone
);


ALTER TABLE public.classifications OWNER TO custom_user;

--
-- Name: classifications_id_seq; Type: SEQUENCE; Schema: public; Owner: custom_user
--

CREATE SEQUENCE public.classifications_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.classifications_id_seq OWNER TO custom_user;

--
-- Name: classifications_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: custom_user
--

ALTER SEQUENCE public.classifications_id_seq OWNED BY public.classifications.id;


--
-- Name: clients; Type: TABLE; Schema: public; Owner: custom_user
--

CREATE TABLE public.clients (
    id integer NOT NULL,
    client_name text,
    campaign_name text,
    created_date timestamp with time zone,
    notes text,
    document_id integer
);


ALTER TABLE public.clients OWNER TO custom_user;

--
-- Name: clients_id_seq; Type: SEQUENCE; Schema: public; Owner: custom_user
--

CREATE SEQUENCE public.clients_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.clients_id_seq OWNER TO custom_user;

--
-- Name: clients_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: custom_user
--

ALTER SEQUENCE public.clients_id_seq OWNED BY public.clients.id;


--
-- Name: communication_focus; Type: TABLE; Schema: public; Owner: custom_user
--

CREATE TABLE public.communication_focus (
    id integer NOT NULL,
    document_id integer,
    primary_issue text,
    secondary_issues text,
    messaging_strategy text,
    created_date timestamp with time zone
);


ALTER TABLE public.communication_focus OWNER TO custom_user;

--
-- Name: communication_focus_id_seq; Type: SEQUENCE; Schema: public; Owner: custom_user
--

CREATE SEQUENCE public.communication_focus_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.communication_focus_id_seq OWNER TO custom_user;

--
-- Name: communication_focus_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: custom_user
--

ALTER SEQUENCE public.communication_focus_id_seq OWNED BY public.communication_focus.id;


--
-- Name: design_elements; Type: TABLE; Schema: public; Owner: custom_user
--

CREATE TABLE public.design_elements (
    id integer NOT NULL,
    document_id integer,
    color_scheme text,
    theme text,
    mail_piece_type text,
    geographic_location text,
    target_audience text,
    campaign_name text,
    confidence bigint,
    created_date timestamp with time zone,
    visual_elements text
);


ALTER TABLE public.design_elements OWNER TO custom_user;

--
-- Name: design_elements_id_seq; Type: SEQUENCE; Schema: public; Owner: custom_user
--

CREATE SEQUENCE public.design_elements_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.design_elements_id_seq OWNER TO custom_user;

--
-- Name: design_elements_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: custom_user
--

ALTER SEQUENCE public.design_elements_id_seq OWNED BY public.design_elements.id;


--
-- Name: document_keywords; Type: TABLE; Schema: public; Owner: custom_user
--

CREATE TABLE public.document_keywords (
    id integer NOT NULL,
    document_id integer,
    taxonomy_id integer,
    relevance_score double precision,
    extraction_date timestamp with time zone
);


ALTER TABLE public.document_keywords OWNER TO custom_user;

--
-- Name: document_keywords_id_seq; Type: SEQUENCE; Schema: public; Owner: custom_user
--

CREATE SEQUENCE public.document_keywords_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.document_keywords_id_seq OWNER TO custom_user;

--
-- Name: document_keywords_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: custom_user
--

ALTER SEQUENCE public.document_keywords_id_seq OWNED BY public.document_keywords.id;


--
-- Name: documents; Type: TABLE; Schema: public; Owner: custom_user
--

CREATE TABLE public.documents (
    id integer NOT NULL,
    filename text NOT NULL,
    upload_date timestamp with time zone NOT NULL,
    file_size bigint NOT NULL,
    page_count integer NOT NULL,
    status text NOT NULL,
    batch_jobs_id integer,
    processing_time double precision,
    search_vector tsvector,
    embeddings public.vector(1536)
);


ALTER TABLE public.documents OWNER TO custom_user;

--
-- Name: documents_id_seq; Type: SEQUENCE; Schema: public; Owner: custom_user
--

CREATE SEQUENCE public.documents_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.documents_id_seq OWNER TO custom_user;

--
-- Name: documents_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: custom_user
--

ALTER SEQUENCE public.documents_id_seq OWNED BY public.documents.id;


--
-- Name: dropbox_syncs; Type: TABLE; Schema: public; Owner: custom_user
--

CREATE TABLE public.dropbox_syncs (
    id integer NOT NULL,
    document_id integer,
    dropbox_file_id character varying(255),
    dropbox_path character varying(512),
    sync_date timestamp with time zone,
    status character varying(50)
);


ALTER TABLE public.dropbox_syncs OWNER TO custom_user;

--
-- Name: dropbox_syncs_id_seq; Type: SEQUENCE; Schema: public; Owner: custom_user
--

CREATE SEQUENCE public.dropbox_syncs_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.dropbox_syncs_id_seq OWNER TO custom_user;

--
-- Name: dropbox_syncs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: custom_user
--

ALTER SEQUENCE public.dropbox_syncs_id_seq OWNED BY public.dropbox_syncs.id;


--
-- Name: entities; Type: TABLE; Schema: public; Owner: custom_user
--

CREATE TABLE public.entities (
    id integer NOT NULL,
    document_id integer,
    client_name text,
    opponent_name text,
    creation_date text,
    survey_question text,
    file_identifier text,
    created_date timestamp with time zone
);


ALTER TABLE public.entities OWNER TO custom_user;

--
-- Name: entities_id_seq; Type: SEQUENCE; Schema: public; Owner: custom_user
--

CREATE SEQUENCE public.entities_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.entities_id_seq OWNER TO custom_user;

--
-- Name: entities_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: custom_user
--

ALTER SEQUENCE public.entities_id_seq OWNED BY public.entities.id;


--
-- Name: extracted_text; Type: TABLE; Schema: public; Owner: custom_user
--

CREATE TABLE public.extracted_text (
    id integer NOT NULL,
    document_id integer,
    page_number integer,
    text_content text,
    confidence bigint,
    extraction_date timestamp with time zone,
    main_message text,
    supporting_text text,
    call_to_action text,
    candidate_name text,
    opponent_name text,
    search_vector tsvector
);


ALTER TABLE public.extracted_text OWNER TO custom_user;

--
-- Name: extracted_text_id_seq; Type: SEQUENCE; Schema: public; Owner: custom_user
--

CREATE SEQUENCE public.extracted_text_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.extracted_text_id_seq OWNER TO custom_user;

--
-- Name: extracted_text_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: custom_user
--

ALTER SEQUENCE public.extracted_text_id_seq OWNED BY public.extracted_text.id;


--
-- Name: keyword_synonyms; Type: TABLE; Schema: public; Owner: custom_user
--

CREATE TABLE public.keyword_synonyms (
    id integer NOT NULL,
    taxonomy_id integer,
    synonym text NOT NULL
);


ALTER TABLE public.keyword_synonyms OWNER TO custom_user;

--
-- Name: keyword_synonyms_id_seq; Type: SEQUENCE; Schema: public; Owner: custom_user
--

CREATE SEQUENCE public.keyword_synonyms_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.keyword_synonyms_id_seq OWNER TO custom_user;

--
-- Name: keyword_synonyms_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: custom_user
--

ALTER SEQUENCE public.keyword_synonyms_id_seq OWNED BY public.keyword_synonyms.id;


--
-- Name: keyword_taxonomy; Type: TABLE; Schema: public; Owner: custom_user
--

CREATE TABLE public.keyword_taxonomy (
    id integer NOT NULL,
    term text NOT NULL,
    primary_category text NOT NULL,
    subcategory text,
    specific_term text,
    description text,
    created_date timestamp with time zone,
    parent_id integer
);


ALTER TABLE public.keyword_taxonomy OWNER TO custom_user;

--
-- Name: keyword_taxonomy_id_seq; Type: SEQUENCE; Schema: public; Owner: custom_user
--

CREATE SEQUENCE public.keyword_taxonomy_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.keyword_taxonomy_id_seq OWNER TO custom_user;

--
-- Name: keyword_taxonomy_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: custom_user
--

ALTER SEQUENCE public.keyword_taxonomy_id_seq OWNED BY public.keyword_taxonomy.id;


--
-- Name: llm_analysis; Type: TABLE; Schema: public; Owner: custom_user
--

CREATE TABLE public.llm_analysis (
    id integer NOT NULL,
    document_id integer,
    summary_description text,
    visual_analysis text,
    content_analysis text,
    confidence_score double precision,
    analysis_date timestamp with time zone,
    model_version text,
    campaign_type text,
    election_year text,
    document_tone text,
    search_vector tsvector,
    embeddings public.vector(1536)
);


ALTER TABLE public.llm_analysis OWNER TO custom_user;

--
-- Name: llm_analysis_id_seq; Type: SEQUENCE; Schema: public; Owner: custom_user
--

CREATE SEQUENCE public.llm_analysis_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.llm_analysis_id_seq OWNER TO custom_user;

--
-- Name: llm_analysis_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: custom_user
--

ALTER SEQUENCE public.llm_analysis_id_seq OWNED BY public.llm_analysis.id;


--
-- Name: llm_keywords; Type: TABLE; Schema: public; Owner: custom_user
--

CREATE TABLE public.llm_keywords (
    id integer NOT NULL,
    llm_analysis_id integer,
    keyword text,
    category text,
    relevance_score bigint
);


ALTER TABLE public.llm_keywords OWNER TO custom_user;

--
-- Name: llm_keywords_id_seq; Type: SEQUENCE; Schema: public; Owner: custom_user
--

CREATE SEQUENCE public.llm_keywords_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.llm_keywords_id_seq OWNER TO custom_user;

--
-- Name: llm_keywords_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: custom_user
--

ALTER SEQUENCE public.llm_keywords_id_seq OWNED BY public.llm_keywords.id;


--
-- Name: search_feedback; Type: TABLE; Schema: public; Owner: custom_user
--

CREATE TABLE public.search_feedback (
    id integer NOT NULL,
    search_query text NOT NULL,
    document_id integer,
    feedback_type character varying(50),
    feedback_date timestamp with time zone,
    user_comment text
);


ALTER TABLE public.search_feedback OWNER TO custom_user;

--
-- Name: search_feedback_id_seq; Type: SEQUENCE; Schema: public; Owner: custom_user
--

CREATE SEQUENCE public.search_feedback_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.search_feedback_id_seq OWNER TO custom_user;

--
-- Name: search_feedback_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: custom_user
--

ALTER SEQUENCE public.search_feedback_id_seq OWNED BY public.search_feedback.id;


--
-- Name: batch_jobs id; Type: DEFAULT; Schema: public; Owner: custom_user
--

ALTER TABLE ONLY public.batch_jobs ALTER COLUMN id SET DEFAULT nextval('public.batch_jobs_id_seq'::regclass);


--
-- Name: classifications id; Type: DEFAULT; Schema: public; Owner: custom_user
--

ALTER TABLE ONLY public.classifications ALTER COLUMN id SET DEFAULT nextval('public.classifications_id_seq'::regclass);


--
-- Name: clients id; Type: DEFAULT; Schema: public; Owner: custom_user
--

ALTER TABLE ONLY public.clients ALTER COLUMN id SET DEFAULT nextval('public.clients_id_seq'::regclass);


--
-- Name: communication_focus id; Type: DEFAULT; Schema: public; Owner: custom_user
--

ALTER TABLE ONLY public.communication_focus ALTER COLUMN id SET DEFAULT nextval('public.communication_focus_id_seq'::regclass);


--
-- Name: design_elements id; Type: DEFAULT; Schema: public; Owner: custom_user
--

ALTER TABLE ONLY public.design_elements ALTER COLUMN id SET DEFAULT nextval('public.design_elements_id_seq'::regclass);


--
-- Name: document_keywords id; Type: DEFAULT; Schema: public; Owner: custom_user
--

ALTER TABLE ONLY public.document_keywords ALTER COLUMN id SET DEFAULT nextval('public.document_keywords_id_seq'::regclass);


--
-- Name: documents id; Type: DEFAULT; Schema: public; Owner: custom_user
--

ALTER TABLE ONLY public.documents ALTER COLUMN id SET DEFAULT nextval('public.documents_id_seq'::regclass);


--
-- Name: dropbox_syncs id; Type: DEFAULT; Schema: public; Owner: custom_user
--

ALTER TABLE ONLY public.dropbox_syncs ALTER COLUMN id SET DEFAULT nextval('public.dropbox_syncs_id_seq'::regclass);


--
-- Name: entities id; Type: DEFAULT; Schema: public; Owner: custom_user
--

ALTER TABLE ONLY public.entities ALTER COLUMN id SET DEFAULT nextval('public.entities_id_seq'::regclass);


--
-- Name: extracted_text id; Type: DEFAULT; Schema: public; Owner: custom_user
--

ALTER TABLE ONLY public.extracted_text ALTER COLUMN id SET DEFAULT nextval('public.extracted_text_id_seq'::regclass);


--
-- Name: keyword_synonyms id; Type: DEFAULT; Schema: public; Owner: custom_user
--

ALTER TABLE ONLY public.keyword_synonyms ALTER COLUMN id SET DEFAULT nextval('public.keyword_synonyms_id_seq'::regclass);


--
-- Name: keyword_taxonomy id; Type: DEFAULT; Schema: public; Owner: custom_user
--

ALTER TABLE ONLY public.keyword_taxonomy ALTER COLUMN id SET DEFAULT nextval('public.keyword_taxonomy_id_seq'::regclass);


--
-- Name: llm_analysis id; Type: DEFAULT; Schema: public; Owner: custom_user
--

ALTER TABLE ONLY public.llm_analysis ALTER COLUMN id SET DEFAULT nextval('public.llm_analysis_id_seq'::regclass);


--
-- Name: llm_keywords id; Type: DEFAULT; Schema: public; Owner: custom_user
--

ALTER TABLE ONLY public.llm_keywords ALTER COLUMN id SET DEFAULT nextval('public.llm_keywords_id_seq'::regclass);


--
-- Name: search_feedback id; Type: DEFAULT; Schema: public; Owner: custom_user
--

ALTER TABLE ONLY public.search_feedback ALTER COLUMN id SET DEFAULT nextval('public.search_feedback_id_seq'::regclass);


--
-- Name: batch_jobs batch_jobs_pkey; Type: CONSTRAINT; Schema: public; Owner: custom_user
--

ALTER TABLE ONLY public.batch_jobs
    ADD CONSTRAINT batch_jobs_pkey PRIMARY KEY (id);


--
-- Name: classifications classifications_pkey; Type: CONSTRAINT; Schema: public; Owner: custom_user
--

ALTER TABLE ONLY public.classifications
    ADD CONSTRAINT classifications_pkey PRIMARY KEY (id);


--
-- Name: clients clients_pkey; Type: CONSTRAINT; Schema: public; Owner: custom_user
--

ALTER TABLE ONLY public.clients
    ADD CONSTRAINT clients_pkey PRIMARY KEY (id);


--
-- Name: communication_focus communication_focus_pkey; Type: CONSTRAINT; Schema: public; Owner: custom_user
--

ALTER TABLE ONLY public.communication_focus
    ADD CONSTRAINT communication_focus_pkey PRIMARY KEY (id);


--
-- Name: design_elements design_elements_pkey; Type: CONSTRAINT; Schema: public; Owner: custom_user
--

ALTER TABLE ONLY public.design_elements
    ADD CONSTRAINT design_elements_pkey PRIMARY KEY (id);


--
-- Name: document_keywords document_keywords_pkey; Type: CONSTRAINT; Schema: public; Owner: custom_user
--

ALTER TABLE ONLY public.document_keywords
    ADD CONSTRAINT document_keywords_pkey PRIMARY KEY (id);


--
-- Name: documents documents_pkey; Type: CONSTRAINT; Schema: public; Owner: custom_user
--

ALTER TABLE ONLY public.documents
    ADD CONSTRAINT documents_pkey PRIMARY KEY (id);


--
-- Name: dropbox_syncs dropbox_syncs_dropbox_file_id_key; Type: CONSTRAINT; Schema: public; Owner: custom_user
--

ALTER TABLE ONLY public.dropbox_syncs
    ADD CONSTRAINT dropbox_syncs_dropbox_file_id_key UNIQUE (dropbox_file_id);


--
-- Name: dropbox_syncs dropbox_syncs_pkey; Type: CONSTRAINT; Schema: public; Owner: custom_user
--

ALTER TABLE ONLY public.dropbox_syncs
    ADD CONSTRAINT dropbox_syncs_pkey PRIMARY KEY (id);


--
-- Name: entities entities_pkey; Type: CONSTRAINT; Schema: public; Owner: custom_user
--

ALTER TABLE ONLY public.entities
    ADD CONSTRAINT entities_pkey PRIMARY KEY (id);


--
-- Name: extracted_text extracted_text_pkey; Type: CONSTRAINT; Schema: public; Owner: custom_user
--

ALTER TABLE ONLY public.extracted_text
    ADD CONSTRAINT extracted_text_pkey PRIMARY KEY (id);


--
-- Name: keyword_synonyms keyword_synonyms_pkey; Type: CONSTRAINT; Schema: public; Owner: custom_user
--

ALTER TABLE ONLY public.keyword_synonyms
    ADD CONSTRAINT keyword_synonyms_pkey PRIMARY KEY (id);


--
-- Name: keyword_taxonomy keyword_taxonomy_pkey; Type: CONSTRAINT; Schema: public; Owner: custom_user
--

ALTER TABLE ONLY public.keyword_taxonomy
    ADD CONSTRAINT keyword_taxonomy_pkey PRIMARY KEY (id);


--
-- Name: llm_analysis llm_analysis_pkey; Type: CONSTRAINT; Schema: public; Owner: custom_user
--

ALTER TABLE ONLY public.llm_analysis
    ADD CONSTRAINT llm_analysis_pkey PRIMARY KEY (id);


--
-- Name: llm_keywords llm_keywords_pkey; Type: CONSTRAINT; Schema: public; Owner: custom_user
--

ALTER TABLE ONLY public.llm_keywords
    ADD CONSTRAINT llm_keywords_pkey PRIMARY KEY (id);


--
-- Name: search_feedback search_feedback_pkey; Type: CONSTRAINT; Schema: public; Owner: custom_user
--

ALTER TABLE ONLY public.search_feedback
    ADD CONSTRAINT search_feedback_pkey PRIMARY KEY (id);


--
-- Name: documents_embeddings_idx; Type: INDEX; Schema: public; Owner: custom_user
--

CREATE INDEX documents_embeddings_idx ON public.documents USING ivfflat (embeddings public.vector_cosine_ops) WITH (lists='100');


--
-- Name: ix_classifications_category; Type: INDEX; Schema: public; Owner: custom_user
--

CREATE INDEX ix_classifications_category ON public.classifications USING btree (category);


--
-- Name: ix_classifications_document_id; Type: INDEX; Schema: public; Owner: custom_user
--

CREATE INDEX ix_classifications_document_id ON public.classifications USING btree (document_id);


--
-- Name: ix_communication_focus_document_id; Type: INDEX; Schema: public; Owner: custom_user
--

CREATE INDEX ix_communication_focus_document_id ON public.communication_focus USING btree (document_id);


--
-- Name: ix_communication_focus_primary_issue; Type: INDEX; Schema: public; Owner: custom_user
--

CREATE INDEX ix_communication_focus_primary_issue ON public.communication_focus USING btree (primary_issue);


--
-- Name: ix_design_elements_document_id; Type: INDEX; Schema: public; Owner: custom_user
--

CREATE INDEX ix_design_elements_document_id ON public.design_elements USING btree (document_id);


--
-- Name: ix_design_elements_geographic_location; Type: INDEX; Schema: public; Owner: custom_user
--

CREATE INDEX ix_design_elements_geographic_location ON public.design_elements USING btree (geographic_location);


--
-- Name: ix_document_keywords_document_id; Type: INDEX; Schema: public; Owner: custom_user
--

CREATE INDEX ix_document_keywords_document_id ON public.document_keywords USING btree (document_id);


--
-- Name: ix_document_keywords_taxonomy_id; Type: INDEX; Schema: public; Owner: custom_user
--

CREATE INDEX ix_document_keywords_taxonomy_id ON public.document_keywords USING btree (taxonomy_id);


--
-- Name: ix_documents_filename; Type: INDEX; Schema: public; Owner: custom_user
--

CREATE INDEX ix_documents_filename ON public.documents USING btree (filename);


--
-- Name: ix_documents_search_vector; Type: INDEX; Schema: public; Owner: custom_user
--

CREATE INDEX ix_documents_search_vector ON public.documents USING gin (search_vector);


--
-- Name: ix_documents_status; Type: INDEX; Schema: public; Owner: custom_user
--

CREATE INDEX ix_documents_status ON public.documents USING btree (status);


--
-- Name: ix_documents_upload_date; Type: INDEX; Schema: public; Owner: custom_user
--

CREATE INDEX ix_documents_upload_date ON public.documents USING btree (upload_date);


--
-- Name: ix_entities_client_name; Type: INDEX; Schema: public; Owner: custom_user
--

CREATE INDEX ix_entities_client_name ON public.entities USING btree (client_name);


--
-- Name: ix_entities_document_id; Type: INDEX; Schema: public; Owner: custom_user
--

CREATE INDEX ix_entities_document_id ON public.entities USING btree (document_id);


--
-- Name: ix_entities_opponent_name; Type: INDEX; Schema: public; Owner: custom_user
--

CREATE INDEX ix_entities_opponent_name ON public.entities USING btree (opponent_name);


--
-- Name: ix_extracted_text_document_id; Type: INDEX; Schema: public; Owner: custom_user
--

CREATE INDEX ix_extracted_text_document_id ON public.extracted_text USING btree (document_id);


--
-- Name: ix_extracted_text_main_message; Type: INDEX; Schema: public; Owner: custom_user
--

CREATE INDEX ix_extracted_text_main_message ON public.extracted_text USING btree (main_message);


--
-- Name: ix_extracted_text_search_vector; Type: INDEX; Schema: public; Owner: custom_user
--

CREATE INDEX ix_extracted_text_search_vector ON public.extracted_text USING gin (search_vector);


--
-- Name: ix_extracted_text_supporting_text; Type: INDEX; Schema: public; Owner: custom_user
--

CREATE INDEX ix_extracted_text_supporting_text ON public.extracted_text USING btree (supporting_text);


--
-- Name: ix_keyword_synonyms_synonym; Type: INDEX; Schema: public; Owner: custom_user
--

CREATE INDEX ix_keyword_synonyms_synonym ON public.keyword_synonyms USING btree (synonym);


--
-- Name: ix_keyword_synonyms_taxonomy_id; Type: INDEX; Schema: public; Owner: custom_user
--

CREATE INDEX ix_keyword_synonyms_taxonomy_id ON public.keyword_synonyms USING btree (taxonomy_id);


--
-- Name: ix_keyword_taxonomy_primary_category; Type: INDEX; Schema: public; Owner: custom_user
--

CREATE INDEX ix_keyword_taxonomy_primary_category ON public.keyword_taxonomy USING btree (primary_category);


--
-- Name: ix_keyword_taxonomy_subcategory; Type: INDEX; Schema: public; Owner: custom_user
--

CREATE INDEX ix_keyword_taxonomy_subcategory ON public.keyword_taxonomy USING btree (subcategory);


--
-- Name: ix_keyword_taxonomy_term; Type: INDEX; Schema: public; Owner: custom_user
--

CREATE INDEX ix_keyword_taxonomy_term ON public.keyword_taxonomy USING btree (term);


--
-- Name: ix_llm_analysis_campaign_type; Type: INDEX; Schema: public; Owner: custom_user
--

CREATE INDEX ix_llm_analysis_campaign_type ON public.llm_analysis USING btree (campaign_type);


--
-- Name: ix_llm_analysis_document_id; Type: INDEX; Schema: public; Owner: custom_user
--

CREATE INDEX ix_llm_analysis_document_id ON public.llm_analysis USING btree (document_id);


--
-- Name: ix_llm_analysis_document_tone; Type: INDEX; Schema: public; Owner: custom_user
--

CREATE INDEX ix_llm_analysis_document_tone ON public.llm_analysis USING btree (document_tone);


--
-- Name: ix_llm_analysis_election_year; Type: INDEX; Schema: public; Owner: custom_user
--

CREATE INDEX ix_llm_analysis_election_year ON public.llm_analysis USING btree (election_year);


--
-- Name: ix_llm_analysis_search_vector; Type: INDEX; Schema: public; Owner: custom_user
--

CREATE INDEX ix_llm_analysis_search_vector ON public.llm_analysis USING gin (search_vector);


--
-- Name: ix_llm_analysis_summary; Type: INDEX; Schema: public; Owner: custom_user
--

CREATE INDEX ix_llm_analysis_summary ON public.llm_analysis USING btree (summary_description);


--
-- Name: ix_llm_keywords_analysis_id; Type: INDEX; Schema: public; Owner: custom_user
--

CREATE INDEX ix_llm_keywords_analysis_id ON public.llm_keywords USING btree (llm_analysis_id);


--
-- Name: ix_llm_keywords_keyword; Type: INDEX; Schema: public; Owner: custom_user
--

CREATE INDEX ix_llm_keywords_keyword ON public.llm_keywords USING btree (keyword);


--
-- Name: llm_analysis_embeddings_idx; Type: INDEX; Schema: public; Owner: custom_user
--

CREATE INDEX llm_analysis_embeddings_idx ON public.llm_analysis USING ivfflat (embeddings public.vector_cosine_ops) WITH (lists='100');


--
-- Name: documents documents_search_vector_update; Type: TRIGGER; Schema: public; Owner: custom_user
--

CREATE TRIGGER documents_search_vector_update BEFORE INSERT OR UPDATE ON public.documents FOR EACH ROW EXECUTE FUNCTION public.documents_search_vector_update();


--
-- Name: extracted_text extracted_text_search_vector_update; Type: TRIGGER; Schema: public; Owner: custom_user
--

CREATE TRIGGER extracted_text_search_vector_update BEFORE INSERT OR UPDATE ON public.extracted_text FOR EACH ROW EXECUTE FUNCTION public.extracted_text_search_vector_update();


--
-- Name: llm_analysis llm_analysis_search_vector_update; Type: TRIGGER; Schema: public; Owner: custom_user
--

CREATE TRIGGER llm_analysis_search_vector_update BEFORE INSERT OR UPDATE ON public.llm_analysis FOR EACH ROW EXECUTE FUNCTION public.llm_analysis_search_vector_update();


--
-- Name: classifications classifications_document_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: custom_user
--

ALTER TABLE ONLY public.classifications
    ADD CONSTRAINT classifications_document_id_fkey FOREIGN KEY (document_id) REFERENCES public.documents(id);


--
-- Name: clients clients_document_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: custom_user
--

ALTER TABLE ONLY public.clients
    ADD CONSTRAINT clients_document_id_fkey FOREIGN KEY (document_id) REFERENCES public.documents(id);


--
-- Name: communication_focus communication_focus_document_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: custom_user
--

ALTER TABLE ONLY public.communication_focus
    ADD CONSTRAINT communication_focus_document_id_fkey FOREIGN KEY (document_id) REFERENCES public.documents(id);


--
-- Name: design_elements design_elements_document_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: custom_user
--

ALTER TABLE ONLY public.design_elements
    ADD CONSTRAINT design_elements_document_id_fkey FOREIGN KEY (document_id) REFERENCES public.documents(id);


--
-- Name: document_keywords document_keywords_document_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: custom_user
--

ALTER TABLE ONLY public.document_keywords
    ADD CONSTRAINT document_keywords_document_id_fkey FOREIGN KEY (document_id) REFERENCES public.documents(id);


--
-- Name: document_keywords document_keywords_taxonomy_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: custom_user
--

ALTER TABLE ONLY public.document_keywords
    ADD CONSTRAINT document_keywords_taxonomy_id_fkey FOREIGN KEY (taxonomy_id) REFERENCES public.keyword_taxonomy(id);


--
-- Name: documents documents_batch_jobs_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: custom_user
--

ALTER TABLE ONLY public.documents
    ADD CONSTRAINT documents_batch_jobs_id_fkey FOREIGN KEY (batch_jobs_id) REFERENCES public.batch_jobs(id);


--
-- Name: dropbox_syncs dropbox_syncs_document_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: custom_user
--

ALTER TABLE ONLY public.dropbox_syncs
    ADD CONSTRAINT dropbox_syncs_document_id_fkey FOREIGN KEY (document_id) REFERENCES public.documents(id);


--
-- Name: entities entities_document_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: custom_user
--

ALTER TABLE ONLY public.entities
    ADD CONSTRAINT entities_document_id_fkey FOREIGN KEY (document_id) REFERENCES public.documents(id);


--
-- Name: extracted_text extracted_text_document_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: custom_user
--

ALTER TABLE ONLY public.extracted_text
    ADD CONSTRAINT extracted_text_document_id_fkey FOREIGN KEY (document_id) REFERENCES public.documents(id);


--
-- Name: keyword_synonyms keyword_synonyms_taxonomy_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: custom_user
--

ALTER TABLE ONLY public.keyword_synonyms
    ADD CONSTRAINT keyword_synonyms_taxonomy_id_fkey FOREIGN KEY (taxonomy_id) REFERENCES public.keyword_taxonomy(id);


--
-- Name: keyword_taxonomy keyword_taxonomy_parent_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: custom_user
--

ALTER TABLE ONLY public.keyword_taxonomy
    ADD CONSTRAINT keyword_taxonomy_parent_id_fkey FOREIGN KEY (parent_id) REFERENCES public.keyword_taxonomy(id);


--
-- Name: llm_analysis llm_analysis_document_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: custom_user
--

ALTER TABLE ONLY public.llm_analysis
    ADD CONSTRAINT llm_analysis_document_id_fkey FOREIGN KEY (document_id) REFERENCES public.documents(id);


--
-- Name: llm_keywords llm_keywords_llm_analysis_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: custom_user
--

ALTER TABLE ONLY public.llm_keywords
    ADD CONSTRAINT llm_keywords_llm_analysis_id_fkey FOREIGN KEY (llm_analysis_id) REFERENCES public.llm_analysis(id);


--
-- Name: search_feedback search_feedback_document_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: custom_user
--

ALTER TABLE ONLY public.search_feedback
    ADD CONSTRAINT search_feedback_document_id_fkey FOREIGN KEY (document_id) REFERENCES public.documents(id);


--
-- PostgreSQL database dump complete
--


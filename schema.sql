-- ============================================================================
-- Bhulekha Extension Database Schema
-- ============================================================================
-- This schema supports multi-model extraction and comparison for Khatiyan
-- land records from the Bhulekh website.
--
-- Design Goals:
-- 1. Store raw page content once, extractions separately
-- 2. Support multiple AI models (Claude, GPT-4, Mistral, etc.)
-- 3. Track prompt versions for DSPy optimization
-- 4. Enable model comparison and A/B testing
-- 5. Track performance metrics (time, cost, accuracy)
-- ============================================================================

-- ============================================================================
-- Drop existing objects (for clean reinstall)
-- ============================================================================

-- Drop views first (they depend on tables)
DROP VIEW IF EXISTS common_matching_failures CASCADE;
DROP VIEW IF EXISTS location_matching_stats CASCADE;
DROP VIEW IF EXISTS unresolved_location_failures CASCADE;
DROP VIEW IF EXISTS extraction_details CASCADE;
DROP VIEW IF EXISTS model_accuracy CASCADE;
DROP VIEW IF EXISTS latest_extractions CASCADE;

-- Drop triggers
DROP TRIGGER IF EXISTS trg_audit_location_matching ON khatiyan_records;
DROP TRIGGER IF EXISTS trg_populate_khatiyan_location_ids ON khatiyan_records;
DROP TRIGGER IF EXISTS update_khatiyan_extractions_updated_at ON khatiyan_extractions;
DROP TRIGGER IF EXISTS update_khatiyan_records_updated_at ON khatiyan_records;

-- Drop functions
DROP FUNCTION IF EXISTS audit_location_matching() CASCADE;
DROP FUNCTION IF EXISTS populate_khatiyan_location_ids() CASCADE;
DROP FUNCTION IF EXISTS update_updated_at_column() CASCADE;

-- Drop tables (in reverse dependency order)
DROP TABLE IF EXISTS location_matching_audit CASCADE;
DROP TABLE IF EXISTS prompt_optimizations CASCADE;
DROP TABLE IF EXISTS khatiyan_extractions CASCADE;
DROP TABLE IF EXISTS khatiyan_records CASCADE;
DROP TABLE IF EXISTS page_contexts CASCADE;

-- ============================================================================
-- Table: page_contexts
-- ============================================================================
-- Stores chat session contexts for Lambda deployment
-- Replaces in-memory storage to support stateless Lambda containers

CREATE TABLE page_contexts (
  id BIGSERIAL PRIMARY KEY,

  -- Page identification
  url TEXT NOT NULL UNIQUE,
  title TEXT NOT NULL,

  -- Content storage
  text_content TEXT NOT NULL,
  html_content TEXT,

  -- Metadata
  word_count INTEGER,
  char_count INTEGER,

  -- Timestamps
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  last_accessed TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Index for fast URL lookups
CREATE INDEX idx_page_contexts_url ON page_contexts(url);

-- Index for cleanup queries (old contexts)
CREATE INDEX idx_page_contexts_created_at ON page_contexts(created_at);
CREATE INDEX idx_page_contexts_last_accessed ON page_contexts(last_accessed);

-- ============================================================================
-- Table: khatiyan_records
-- ============================================================================
-- Stores unique Bhulekh webpage records with raw content
-- One record per unique (district, tehsil, village, khatiyan_number) combination

CREATE TABLE khatiyan_records (
  id BIGSERIAL PRIMARY KEY,

  -- Khatiyan identification (unique key components)
  district TEXT NOT NULL,
  tehsil TEXT NOT NULL,
  village TEXT NOT NULL,
  khatiyan_number TEXT NOT NULL,

  -- Native language names (e.g., Odia script)
  native_district TEXT,
  native_tehsil TEXT,
  native_village TEXT,

  -- Location IDs (auto-populated by trigger from master tables)
  district_id BIGINT,  -- References districts table
  tehsil_id BIGINT,    -- References tahasils table
  village_id BIGINT,   -- References villages table

  -- Source IDs (auto-populated by trigger - copied from master tables)
  district_source_id BIGINT,  -- source_id from districts table
  tehsil_source_id BIGINT,    -- source_id from tahasils table
  village_source_id BIGINT,   -- source_id from villages table

  -- Generated URLs (auto-populated by trigger)
  bhulekha_ror_url TEXT,      -- Bhulekha RoR view URL constructed from source_ids

  -- Page metadata
  title TEXT,

  -- Raw content (stored once for all extractions)
  raw_content TEXT,              -- Full text content from page
  raw_html TEXT,                 -- Original HTML (optional, for debugging)

  -- Metadata
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

  -- Ensure we don't duplicate the same khatiyan record
  -- Khatiyan number is unique only within a specific district/tehsil/village combination
  CONSTRAINT unique_khatiyan UNIQUE(district, tehsil, village, khatiyan_number)
);

-- Index for looking up existing records by location (text-based)
CREATE INDEX idx_khatiyan_records_location ON khatiyan_records(district, tehsil, village);
CREATE INDEX idx_khatiyan_records_native_location ON khatiyan_records(native_district, native_tehsil, native_village);
CREATE INDEX idx_khatiyan_records_created ON khatiyan_records(created_at DESC);

-- Indexes for location IDs (for efficient lookups and joins)
CREATE INDEX idx_khatiyan_records_district_id ON khatiyan_records(district_id);
CREATE INDEX idx_khatiyan_records_tehsil_id ON khatiyan_records(tehsil_id);
CREATE INDEX idx_khatiyan_records_village_id ON khatiyan_records(village_id);

-- Composite index for location hierarchy lookups (district -> tehsil -> village)
CREATE INDEX idx_khatiyan_records_location_ids ON khatiyan_records(district_id, tehsil_id, village_id);

-- ============================================================================
-- Table: location_matching_audit
-- ============================================================================
-- Audit log for tracking location name matching attempts (success & failures)
-- Enables analysis of matching patterns and identification of data quality issues

CREATE TABLE location_matching_audit (
  id BIGSERIAL PRIMARY KEY,

  -- Link to the khatiyan record that was being inserted
  khatiyan_record_id BIGINT REFERENCES khatiyan_records(id) ON DELETE CASCADE,

  -- What type of location was being matched
  location_type TEXT NOT NULL CHECK (location_type IN ('village', 'tehsil')),

  -- Input values from khatiyan_records
  native_value TEXT,
  english_value TEXT,

  -- Matching result
  match_status TEXT NOT NULL CHECK (match_status IN ('success', 'failed')),
  matched_id BIGINT,  -- The ID from villages/tahasils table (NULL if failed)
  master_table TEXT CHECK (master_table IN ('villages', 'tahasils')),

  -- Which matching strategy succeeded (for analysis)
  -- Examples: 'native_village->native_name', 'village->english_name', etc.
  matched_by TEXT,

  -- Resolution tracking (for failed matches)
  resolved BOOLEAN DEFAULT FALSE,
  resolution_notes TEXT,
  resolved_by TEXT,  -- User/system who resolved it
  resolved_at TIMESTAMP WITH TIME ZONE,

  -- Timestamp
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes for efficient querying
CREATE INDEX idx_location_audit_khatiyan_id ON location_matching_audit(khatiyan_record_id);
CREATE INDEX idx_location_audit_status ON location_matching_audit(match_status);
CREATE INDEX idx_location_audit_type ON location_matching_audit(location_type);
CREATE INDEX idx_location_audit_unresolved ON location_matching_audit(match_status, resolved) WHERE match_status = 'failed' AND resolved = FALSE;
CREATE INDEX idx_location_audit_created ON location_matching_audit(created_at DESC);

-- Composite index for failure analysis
CREATE INDEX idx_location_audit_failures ON location_matching_audit(location_type, match_status) WHERE match_status = 'failed';

-- ============================================================================
-- Table: khatiyan_extractions
-- ============================================================================
-- Stores AI model extractions from khatiyan records
-- Multiple extractions per record (one per model/prompt version)

CREATE TABLE khatiyan_extractions (
  id BIGSERIAL PRIMARY KEY,

  -- Link to source record
  khatiyan_record_id BIGINT NOT NULL REFERENCES khatiyan_records(id) ON DELETE CASCADE,

  -- Model identification
  model_provider TEXT NOT NULL,  -- 'anthropic', 'openai', 'mistral', 'google', 'html_parser', etc.
  model_name TEXT NOT NULL,      -- 'claude-3-5-sonnet-20241022', 'gpt-4-turbo', 'beautifulsoup4', etc.

  -- Prompt tracking (for DSPy optimization)
  prompt_version TEXT DEFAULT 'v1',  -- Track DSPy signature versions
  prompt_config JSONB,           -- Store DSPy config/optimizer used (includes actual prompt sent to LLM)

  -- Extracted data stored as JSON (extensible schema)
  -- This allows adding new fields without schema migrations
  -- Example structure: {"district": "...", "tehsil": "...", "owner_name": "...", ...}
  extraction_data JSONB NOT NULL,

  -- Quality and validation
  extraction_status TEXT CHECK (extraction_status IN ('pending', 'correct', 'wrong', 'needs_review')),

  -- Extraction method tracking (HTML parser vs LLM)
  extraction_method TEXT CHECK (extraction_method IN ('html_parser', 'llm_fallback', 'llm_only') OR extraction_method IS NULL),
  parser_confidence TEXT CHECK (parser_confidence IN ('high', 'medium', 'low') OR parser_confidence IS NULL),

  -- Performance metrics
  extraction_time_ms INTEGER,    -- Extraction duration in milliseconds

  -- User feedback
  extraction_user_feedback TEXT, -- Optional free-form feedback/comments from users (especially when marking as 'wrong')
  feedback_timestamp TIMESTAMP WITH TIME ZONE,

  -- Metadata
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

  -- Prevent duplicate extractions for same record + model + prompt version
  CONSTRAINT unique_extraction UNIQUE(khatiyan_record_id, model_provider, model_name, prompt_version)
);

-- Indexes for common queries
CREATE INDEX idx_extractions_record ON khatiyan_extractions(khatiyan_record_id);
CREATE INDEX idx_extractions_model ON khatiyan_extractions(model_provider, model_name);
CREATE INDEX idx_extractions_status ON khatiyan_extractions(extraction_status);
CREATE INDEX idx_extractions_prompt ON khatiyan_extractions(prompt_version);
CREATE INDEX idx_extractions_created ON khatiyan_extractions(created_at DESC);
CREATE INDEX idx_extractions_method ON khatiyan_extractions(extraction_method);  -- Monitor parser vs LLM usage

-- Composite index for model comparison queries
CREATE INDEX idx_extractions_comparison ON khatiyan_extractions(khatiyan_record_id, model_name, extraction_status);

-- JSONB indexes for querying extracted data fields
-- GIN index for general JSONB queries
CREATE INDEX idx_extractions_data_gin ON khatiyan_extractions USING GIN (extraction_data);

-- Specific B-tree indexes for commonly queried fields (optional, for better performance on exact matches)
CREATE INDEX idx_extractions_district ON khatiyan_extractions ((extraction_data->>'district'));
CREATE INDEX idx_extractions_khatiyan_number ON khatiyan_extractions ((extraction_data->>'khatiyan_number'));

-- ============================================================================
-- Table: khatiyan_summaries
-- ============================================================================
-- Stores AI-generated RoR summaries separate from extractions
-- Multiple summaries per record (one per model/prompt version)

CREATE TABLE khatiyan_summaries (
  id BIGSERIAL PRIMARY KEY,

  -- Link to source record
  khatiyan_record_id BIGINT NOT NULL REFERENCES khatiyan_records(id) ON DELETE CASCADE,

  -- Model identification
  model_provider TEXT NOT NULL,  -- 'anthropic', 'openai', 'mistral', 'google', etc.
  model_name TEXT NOT NULL,      -- 'claude-3-5-sonnet-20241022', 'gpt-4-turbo', etc.

  -- Prompt tracking (for DSPy optimization)
  prompt_version TEXT DEFAULT 'v1',  -- Track DSPy signature versions
  prompt_config JSONB,           -- Store DSPy config/optimizer used (includes actual prompt sent to LLM)

  -- Generated summary
  summary_html TEXT NOT NULL,    -- HTML-formatted RoR summary with risk assessment

  -- Performance metrics
  generation_time_ms INTEGER,    -- Summary generation duration in milliseconds

  -- Quality and validation
  summarization_status TEXT CHECK (summarization_status IN ('pending', 'correct', 'wrong', 'needs_review')),

  -- User feedback
  summarization_user_feedback TEXT,  -- Optional feedback comments for summaries
  feedback_timestamp TIMESTAMP WITH TIME ZONE,

  -- Metadata
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

  -- Prevent duplicate summaries for same record + model + prompt version
  CONSTRAINT unique_summary UNIQUE(khatiyan_record_id, model_provider, model_name, prompt_version)
);

-- Indexes for common queries
CREATE INDEX idx_summaries_record ON khatiyan_summaries(khatiyan_record_id);
CREATE INDEX idx_summaries_model ON khatiyan_summaries(model_provider, model_name);
CREATE INDEX idx_summaries_status ON khatiyan_summaries(summarization_status);
CREATE INDEX idx_summaries_prompt ON khatiyan_summaries(prompt_version);
CREATE INDEX idx_summaries_created ON khatiyan_summaries(created_at DESC);

-- Composite index for caching lookups (most common query pattern)
CREATE INDEX idx_summaries_cache_lookup ON khatiyan_summaries(khatiyan_record_id, model_name, prompt_version, created_at DESC);

-- ============================================================================
-- Table: prompt_optimizations (Optional - for future use)
-- ============================================================================
-- Track DSPy prompt optimization experiments

CREATE TABLE prompt_optimizations (
  id BIGSERIAL PRIMARY KEY,

  prompt_version TEXT NOT NULL UNIQUE,
  prompt_name TEXT,              -- e.g., 'ExtractKhatiyan', 'ExplainContent'

  -- DSPy optimizer configuration
  optimizer_type TEXT,           -- 'BootstrapFewShot', 'MIPRO', etc.
  optimizer_config JSONB,

  -- Training data
  training_examples_count INTEGER,
  validation_examples_count INTEGER,

  -- Performance metrics
  accuracy_before FLOAT,
  accuracy_after FLOAT,
  improvement FLOAT,

  -- Metadata
  notes TEXT,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  created_by TEXT
);

-- ============================================================================
-- Useful Views
-- ============================================================================

-- View: Latest extraction per record
CREATE VIEW latest_extractions AS
SELECT DISTINCT ON (khatiyan_record_id, model_name)
  ke.*,
  kr.district,
  kr.tehsil,
  kr.village,
  kr.khatiyan_number,
  kr.title
FROM khatiyan_extractions ke
JOIN khatiyan_records kr ON ke.khatiyan_record_id = kr.id
ORDER BY khatiyan_record_id, model_name, created_at DESC;

-- View: Model accuracy comparison (for extractions only)
CREATE VIEW model_accuracy AS
SELECT
  model_provider,
  model_name,
  prompt_version,
  COUNT(*) as total_extractions,
  SUM(CASE WHEN extraction_status = 'correct' THEN 1 ELSE 0 END) as correct_count,
  SUM(CASE WHEN extraction_status = 'wrong' THEN 1 ELSE 0 END) as wrong_count,
  SUM(CASE WHEN extraction_status = 'pending' THEN 1 ELSE 0 END) as pending_count,
  ROUND(
    100.0 * SUM(CASE WHEN extraction_status = 'correct' THEN 1 ELSE 0 END) /
    NULLIF(SUM(CASE WHEN extraction_status IN ('correct', 'wrong') THEN 1 ELSE 0 END), 0),
    2
  ) as accuracy_percentage,
  AVG(extraction_time_ms) as avg_time_ms
FROM khatiyan_extractions
GROUP BY model_provider, model_name, prompt_version
ORDER BY accuracy_percentage DESC NULLS LAST;

-- View: Flattened extraction data (for easier querying)
-- This view extracts commonly used fields from the JSON for convenience
CREATE VIEW extraction_details AS
SELECT
  ke.id,
  ke.khatiyan_record_id,
  kr.district as record_district,
  kr.tehsil as record_tehsil,
  kr.village as record_village,
  kr.khatiyan_number as record_khatiyan_number,
  kr.title,
  ke.model_provider,
  ke.model_name,
  ke.prompt_version,

  -- Extract commonly queried fields from JSON
  ke.extraction_data->>'district' as extracted_district,
  ke.extraction_data->>'tehsil' as extracted_tehsil,
  ke.extraction_data->>'village' as extracted_village,
  ke.extraction_data->>'khatiyan_number' as extracted_khatiyan_number,
  ke.extraction_data->>'owner_name' as owner_name,
  ke.extraction_data->>'father_name' as father_name,
  ke.extraction_data->>'total_plots' as total_plots,
  ke.extraction_data->>'total_area' as total_area,

  -- Keep full JSON for additional fields
  ke.extraction_data,

  ke.extraction_status,
  ke.extraction_time_ms,
  ke.created_at
FROM khatiyan_extractions ke
JOIN khatiyan_records kr ON ke.khatiyan_record_id = kr.id;

-- View: Latest summary per record
CREATE VIEW latest_summaries AS
SELECT DISTINCT ON (khatiyan_record_id, model_name)
  ks.*,
  kr.district,
  kr.tehsil,
  kr.village,
  kr.khatiyan_number,
  kr.title
FROM khatiyan_summaries ks
JOIN khatiyan_records kr ON ks.khatiyan_record_id = kr.id
ORDER BY khatiyan_record_id, model_name, created_at DESC;

-- View: Summary quality comparison
CREATE VIEW summary_accuracy AS
SELECT
  model_provider,
  model_name,
  prompt_version,
  COUNT(*) as total_summaries,
  SUM(CASE WHEN summarization_status = 'correct' THEN 1 ELSE 0 END) as correct_count,
  SUM(CASE WHEN summarization_status = 'wrong' THEN 1 ELSE 0 END) as wrong_count,
  SUM(CASE WHEN summarization_status = 'pending' THEN 1 ELSE 0 END) as pending_count,
  ROUND(
    100.0 * SUM(CASE WHEN summarization_status = 'correct' THEN 1 ELSE 0 END) /
    NULLIF(SUM(CASE WHEN summarization_status IN ('correct', 'wrong') THEN 1 ELSE 0 END), 0),
    2
  ) as accuracy_percentage,
  AVG(generation_time_ms) as avg_time_ms
FROM khatiyan_summaries
GROUP BY model_provider, model_name, prompt_version
ORDER BY accuracy_percentage DESC NULLS LAST;

-- View: Unresolved matching failures
-- Shows all failed matches that haven't been resolved yet
CREATE VIEW unresolved_location_failures AS
SELECT
  lma.id,
  lma.khatiyan_record_id,
  lma.location_type,
  lma.native_value,
  lma.english_value,
  kr.district,
  kr.tehsil,
  kr.village,
  lma.created_at,
  lma.resolution_notes
FROM location_matching_audit lma
JOIN khatiyan_records kr ON lma.khatiyan_record_id = kr.id
WHERE lma.match_status = 'failed'
  AND lma.resolved = FALSE
ORDER BY lma.created_at DESC;

-- View: Matching statistics by location type
CREATE VIEW location_matching_stats AS
SELECT
  location_type,
  COUNT(*) as total_attempts,
  SUM(CASE WHEN match_status = 'success' THEN 1 ELSE 0 END) as successful_matches,
  SUM(CASE WHEN match_status = 'failed' THEN 1 ELSE 0 END) as failed_matches,
  SUM(CASE WHEN match_status = 'failed' AND resolved = FALSE THEN 1 ELSE 0 END) as unresolved_failures,
  ROUND(
    100.0 * SUM(CASE WHEN match_status = 'success' THEN 1 ELSE 0 END) / COUNT(*),
    2
  ) as success_rate_percentage
FROM location_matching_audit
GROUP BY location_type;

-- View: Most common failure patterns
-- Shows which native/english value combinations fail most frequently
CREATE VIEW common_matching_failures AS
SELECT
  location_type,
  native_value,
  english_value,
  COUNT(*) as failure_count,
  MAX(created_at) as last_failed_at,
  SUM(CASE WHEN resolved = TRUE THEN 1 ELSE 0 END) as resolved_count,
  SUM(CASE WHEN resolved = FALSE THEN 1 ELSE 0 END) as unresolved_count
FROM location_matching_audit
WHERE match_status = 'failed'
GROUP BY location_type, native_value, english_value
HAVING COUNT(*) > 1  -- Only show patterns that failed multiple times
ORDER BY failure_count DESC, last_failed_at DESC;

-- View : khatiyan_extractions Evaluation dataset
CREATE OR REPLACE VIEW khatiyan_extraction_eval_dataset AS
        SELECT
            e.id,
            e.khatiyan_record_id,
            r.raw_html as khatiyan_raw_html,
            r.raw_content as khatiyan_raw_text,
            e.prompt_config,
            e.model_name,
            e.extraction_data,
            e.created_at,
            e.updated_at
        FROM khatiyan_extractions e
        INNER JOIN khatiyan_records r ON e.khatiyan_record_id = r.id;
-- ============================================================================
-- Helper Functions
-- ============================================================================

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Triggers to auto-update updated_at
CREATE TRIGGER update_khatiyan_records_updated_at
  BEFORE UPDATE ON khatiyan_records
  FOR EACH ROW
  EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_khatiyan_extractions_updated_at
  BEFORE UPDATE ON khatiyan_extractions
  FOR EACH ROW
  EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_khatiyan_summaries_updated_at
  BEFORE UPDATE ON khatiyan_summaries
  FOR EACH ROW
  EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- Function and Trigger: Auto-populate Location IDs in khatiyan_records
-- ============================================================================
-- Automatically populates district_id, tehsil_id, village_id and their source_ids
-- by matching text names against master tables (districts, tahasils, villages)
--
-- Business Logic (Hierarchical Matching):
-- 1. Match DISTRICT first (unconstrained)
--    - If fails: STOP and log warning
-- 2. Match TEHSIL within the matched district (constrained by district_id)
--    - If fails: STOP and log warning
-- 3. Match VILLAGE within the matched district AND tehsil (constrained by both)
--    - If fails: STOP and log warning
-- 4. Generate Bhulekha RoR URL if all matches succeeded
--
-- Matching Strategy (tries in this order until a match is found):
-- For each location level (district/tehsil/village):
--   1. Try english column → master.english_name
--   2. Try native column → master.english_name
--   3. Try english column → master.native_name
--   4. Try native column → master.native_name
-- All matches are case-insensitive with trimmed whitespace
-- Use LIMIT 1 if multiple matches (takes first)

CREATE OR REPLACE FUNCTION populate_khatiyan_location_ids()
RETURNS TRIGGER AS $$
DECLARE
  matched_district_id bigint;
  matched_district_source_id bigint;
  matched_tehsil_id bigint;
  matched_tehsil_source_id bigint;
  matched_village_id bigint;
  matched_village_source_id bigint;
BEGIN
  -- -------------------------------------------------------------------------
  -- Step 1: Match DISTRICT (unconstrained)
  -- Try English first, then native
  -- -------------------------------------------------------------------------

  -- 1. Try district → districts.english_name
  IF NEW.district IS NOT NULL AND TRIM(NEW.district) != '' THEN
    SELECT id, source_id
    INTO matched_district_id, matched_district_source_id
    FROM districts
    WHERE LOWER(TRIM(english_name)) = LOWER(TRIM(NEW.district))
    LIMIT 1;
  END IF;

  -- 2. Try native_district → districts.english_name
  IF matched_district_id IS NULL AND NEW.native_district IS NOT NULL AND TRIM(NEW.native_district) != '' THEN
    SELECT id, source_id
    INTO matched_district_id, matched_district_source_id
    FROM districts
    WHERE LOWER(TRIM(english_name)) = LOWER(TRIM(NEW.native_district))
    LIMIT 1;
  END IF;

  -- 3. Try district → districts.native_name
  IF matched_district_id IS NULL AND NEW.district IS NOT NULL AND TRIM(NEW.district) != '' THEN
    SELECT id, source_id
    INTO matched_district_id, matched_district_source_id
    FROM districts
    WHERE LOWER(TRIM(native_name)) = LOWER(TRIM(NEW.district))
    LIMIT 1;
  END IF;

  -- 4. Try native_district → districts.native_name
  IF matched_district_id IS NULL AND NEW.native_district IS NOT NULL AND TRIM(NEW.native_district) != '' THEN
    SELECT id, source_id
    INTO matched_district_id, matched_district_source_id
    FROM districts
    WHERE LOWER(TRIM(native_name)) = LOWER(TRIM(NEW.native_district))
    LIMIT 1;
  END IF;

  -- If district match fails, STOP here
  IF matched_district_id IS NULL THEN
    RAISE WARNING 'District matching failed for (district: "%, native_district: "%") - STOPPING',
                  NEW.district, NEW.native_district;
    RETURN NEW;
  END IF;

  -- Populate district IDs
  NEW.district_id := matched_district_id;
  NEW.district_source_id := matched_district_source_id;

  RAISE INFO 'Matched district (district: "%, native_district: "%") → district_id=%, district_source_id=%',
             NEW.district, NEW.native_district, matched_district_id, matched_district_source_id;

  -- -------------------------------------------------------------------------
  -- Step 2: Match TEHSIL (constrained by district_id)
  -- Try English first, then native
  -- -------------------------------------------------------------------------

  -- 1. Try tehsil → tahasils.english_name
  IF NEW.tehsil IS NOT NULL AND TRIM(NEW.tehsil) != '' THEN
    SELECT id, source_id
    INTO matched_tehsil_id, matched_tehsil_source_id
    FROM tahasils
    WHERE LOWER(TRIM(english_name)) = LOWER(TRIM(NEW.tehsil))
      AND district_id = matched_district_id
    LIMIT 1;
  END IF;

  -- 2. Try native_tehsil → tahasils.english_name
  IF matched_tehsil_id IS NULL AND NEW.native_tehsil IS NOT NULL AND TRIM(NEW.native_tehsil) != '' THEN
    SELECT id, source_id
    INTO matched_tehsil_id, matched_tehsil_source_id
    FROM tahasils
    WHERE LOWER(TRIM(english_name)) = LOWER(TRIM(NEW.native_tehsil))
      AND district_id = matched_district_id
    LIMIT 1;
  END IF;

  -- 3. Try tehsil → tahasils.native_name
  IF matched_tehsil_id IS NULL AND NEW.tehsil IS NOT NULL AND TRIM(NEW.tehsil) != '' THEN
    SELECT id, source_id
    INTO matched_tehsil_id, matched_tehsil_source_id
    FROM tahasils
    WHERE LOWER(TRIM(native_name)) = LOWER(TRIM(NEW.tehsil))
      AND district_id = matched_district_id
    LIMIT 1;
  END IF;

  -- 4. Try native_tehsil → tahasils.native_name
  IF matched_tehsil_id IS NULL AND NEW.native_tehsil IS NOT NULL AND TRIM(NEW.native_tehsil) != '' THEN
    SELECT id, source_id
    INTO matched_tehsil_id, matched_tehsil_source_id
    FROM tahasils
    WHERE LOWER(TRIM(native_name)) = LOWER(TRIM(NEW.native_tehsil))
      AND district_id = matched_district_id
    LIMIT 1;
  END IF;

  -- If tehsil match fails, STOP here
  IF matched_tehsil_id IS NULL THEN
    RAISE WARNING 'Tehsil matching failed for (tehsil: "%, native_tehsil: "%") within district_id=% - STOPPING',
                  NEW.tehsil, NEW.native_tehsil, matched_district_id;
    RETURN NEW;
  END IF;

  -- Populate tehsil IDs
  NEW.tehsil_id := matched_tehsil_id;
  NEW.tehsil_source_id := matched_tehsil_source_id;

  RAISE INFO 'Matched tehsil (tehsil: "%, native_tehsil: "%") → tehsil_id=%, tehsil_source_id=%',
             NEW.tehsil, NEW.native_tehsil, matched_tehsil_id, matched_tehsil_source_id;

  -- -------------------------------------------------------------------------
  -- Step 3: Match VILLAGE (constrained by district_id AND tahasil_id)
  -- Try English first, then native
  -- -------------------------------------------------------------------------

  -- 1. Try village → villages.english_name
  IF NEW.village IS NOT NULL AND TRIM(NEW.village) != '' THEN
    SELECT id, source_id
    INTO matched_village_id, matched_village_source_id
    FROM villages
    WHERE LOWER(TRIM(english_name)) = LOWER(TRIM(NEW.village))
      AND district_id = matched_district_id
      AND tahasil_id = matched_tehsil_id
    LIMIT 1;
  END IF;

  -- 2. Try native_village → villages.english_name
  IF matched_village_id IS NULL AND NEW.native_village IS NOT NULL AND TRIM(NEW.native_village) != '' THEN
    SELECT id, source_id
    INTO matched_village_id, matched_village_source_id
    FROM villages
    WHERE LOWER(TRIM(english_name)) = LOWER(TRIM(NEW.native_village))
      AND district_id = matched_district_id
      AND tahasil_id = matched_tehsil_id
    LIMIT 1;
  END IF;

  -- 3. Try village → villages.native_name
  IF matched_village_id IS NULL AND NEW.village IS NOT NULL AND TRIM(NEW.village) != '' THEN
    SELECT id, source_id
    INTO matched_village_id, matched_village_source_id
    FROM villages
    WHERE LOWER(TRIM(native_name)) = LOWER(TRIM(NEW.village))
      AND district_id = matched_district_id
      AND tahasil_id = matched_tehsil_id
    LIMIT 1;
  END IF;

  -- 4. Try native_village → villages.native_name
  IF matched_village_id IS NULL AND NEW.native_village IS NOT NULL AND TRIM(NEW.native_village) != '' THEN
    SELECT id, source_id
    INTO matched_village_id, matched_village_source_id
    FROM villages
    WHERE LOWER(TRIM(native_name)) = LOWER(TRIM(NEW.native_village))
      AND district_id = matched_district_id
      AND tahasil_id = matched_tehsil_id
    LIMIT 1;
  END IF;

  -- If village match fails, STOP here
  IF matched_village_id IS NULL THEN
    RAISE WARNING 'Village matching failed for (village: "%, native_village: "%") within district_id=%, tahasil_id=% - STOPPING',
                  NEW.village, NEW.native_village, matched_district_id, matched_tehsil_id;
    RETURN NEW;
  END IF;

  -- Populate village IDs
  NEW.village_id := matched_village_id;
  NEW.village_source_id := matched_village_source_id;

  RAISE INFO 'Matched village (village: "%, native_village: "%") → village_id=%, village_source_id=%',
             NEW.village, NEW.native_village, matched_village_id, matched_village_source_id;

  -- -------------------------------------------------------------------------
  -- Step 4: Generate Bhulekha RoR URL
  -- -------------------------------------------------------------------------
  -- At this point, all IDs should be populated (we only reach here if all matches succeeded)
  IF NEW.district_source_id IS NOT NULL
     AND NEW.tehsil_source_id IS NOT NULL
     AND NEW.village_source_id IS NOT NULL
     AND NEW.khatiyan_number IS NOT NULL THEN

    NEW.bhulekha_ror_url := 'https://bhulekh.ori.nic.in/ViewRoR.aspx?DistCode='
                         || NEW.district_source_id
                         || '&TehCode=' || NEW.tehsil_source_id
                         || '&VillCode=' || NEW.village_source_id
                         || '&KhataNo=' || NEW.khatiyan_number
                         || '&type=front';

    RAISE INFO 'Generated Bhulekha RoR URL: %', NEW.bhulekha_ror_url;
  ELSE
    RAISE WARNING 'Cannot generate Bhulekha RoR URL - missing required fields (district_source_id: %, tehsil_source_id: %, village_source_id: %, khatiyan_number: %)',
                  NEW.district_source_id, NEW.tehsil_source_id, NEW.village_source_id, NEW.khatiyan_number;
  END IF;

  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger to auto-populate location IDs on INSERT
CREATE TRIGGER trg_populate_khatiyan_location_ids
  BEFORE INSERT ON khatiyan_records
  FOR EACH ROW
  EXECUTE FUNCTION populate_khatiyan_location_ids();

-- ============================================================================
-- Function and Trigger: Audit Location Matching Results
-- ============================================================================
-- Logs all matching attempts (success and failures) to location_matching_audit
-- Runs AFTER INSERT so we have the khatiyan_record_id

CREATE OR REPLACE FUNCTION audit_location_matching()
RETURNS TRIGGER AS $$
BEGIN
  -- Audit VILLAGE matching
  IF NEW.native_village IS NOT NULL OR NEW.village IS NOT NULL THEN
    INSERT INTO location_matching_audit (
      khatiyan_record_id,
      location_type,
      native_value,
      english_value,
      match_status,
      matched_id,
      master_table,
      matched_by
    ) VALUES (
      NEW.id,
      'village',
      NEW.native_village,
      NEW.village,
      CASE WHEN NEW.village_id IS NOT NULL THEN 'success' ELSE 'failed' END,
      NEW.village_id,
      'villages',
      CASE
        WHEN NEW.village_id IS NOT NULL THEN 'matched'
        ELSE NULL
      END
    );
  END IF;

  -- Audit TEHSIL matching
  IF NEW.native_tehsil IS NOT NULL OR NEW.tehsil IS NOT NULL THEN
    INSERT INTO location_matching_audit (
      khatiyan_record_id,
      location_type,
      native_value,
      english_value,
      match_status,
      matched_id,
      master_table,
      matched_by
    ) VALUES (
      NEW.id,
      'tehsil',
      NEW.native_tehsil,
      NEW.tehsil,
      CASE WHEN NEW.tehsil_id IS NOT NULL THEN 'success' ELSE 'failed' END,
      NEW.tehsil_id,
      'tahasils',
      CASE
        WHEN NEW.tehsil_id IS NOT NULL THEN 'matched'
        ELSE NULL
      END
    );
  END IF;

  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger to audit matching results AFTER INSERT
CREATE TRIGGER trg_audit_location_matching
  AFTER INSERT ON khatiyan_records
  FOR EACH ROW
  EXECUTE FUNCTION audit_location_matching();

-- ============================================================================
-- Migration: Add source_id columns to khatiyan_records (for existing databases)
-- ============================================================================
-- Run these ALTER statements if you're upgrading an existing database
-- For new installations, these columns are already in the CREATE TABLE above

-- Add source_id columns
ALTER TABLE khatiyan_records ADD COLUMN IF NOT EXISTS district_source_id BIGINT;
ALTER TABLE khatiyan_records ADD COLUMN IF NOT EXISTS tehsil_source_id BIGINT;
ALTER TABLE khatiyan_records ADD COLUMN IF NOT EXISTS village_source_id BIGINT;
ALTER TABLE khatiyan_records ADD COLUMN IF NOT EXISTS bhulekha_ror_url TEXT;

-- Backfill source_id values for existing records (optional)
-- This will populate source_id columns for records that already have location IDs
UPDATE khatiyan_records kr
SET village_source_id = v.source_id
FROM villages v
WHERE kr.village_id = v.id
  AND kr.village_source_id IS NULL;

UPDATE khatiyan_records kr
SET tehsil_source_id = t.source_id
FROM tahasils t
WHERE kr.tehsil_id = t.id
  AND kr.tehsil_source_id IS NULL;

UPDATE khatiyan_records kr
SET district_source_id = d.source_id
FROM districts d
WHERE kr.district_id = d.id
  AND kr.district_source_id IS NULL;

-- Backfill bhulekha_ror_url for existing records (optional)
-- This will generate URLs for records that have all required source_ids
UPDATE khatiyan_records
SET bhulekha_ror_url = 'https://bhulekh.ori.nic.in/ViewRoR.aspx?DistCode='
                    || district_source_id
                    || '&TehCode=' || tehsil_source_id
                    || '&VillCode=' || village_source_id
                    || '&KhataNo=' || khatiyan_number
                    || '&type=front'
WHERE district_source_id IS NOT NULL
  AND tehsil_source_id IS NOT NULL
  AND village_source_id IS NOT NULL
  AND khatiyan_number IS NOT NULL
  AND bhulekha_ror_url IS NULL;

-- ============================================================================
-- Example Queries
-- ============================================================================

-- Compare Claude vs other models on same record
-- SELECT
--   kr.district, kr.tehsil, kr.village, kr.khatiyan_number,
--   ke1.extraction_data->>'district' as claude_district,
--   ke2.extraction_data->>'district' as gpt4_district,
--   ke1.extraction_status as claude_status,
--   ke2.extraction_status as gpt4_status
-- FROM khatiyan_records kr
-- JOIN khatiyan_extractions ke1 ON kr.id = ke1.khatiyan_record_id
--   AND ke1.model_name LIKE 'claude%'
-- LEFT JOIN khatiyan_extractions ke2 ON kr.id = ke2.khatiyan_record_id
--   AND ke2.model_name LIKE 'gpt%'
-- WHERE ke1.extraction_data->>'district' != ke2.extraction_data->>'district';

-- Find records needing review
-- SELECT
--   id,
--   extraction_data->>'khatiyan_number' as khatiyan_number,
--   extraction_data->>'district' as district,
--   model_name,
--   created_at
-- FROM khatiyan_extractions
-- WHERE extraction_status = 'pending'
-- ORDER BY created_at DESC
-- LIMIT 10;

-- Track prompt improvement over time
-- SELECT
--   prompt_version,
--   COUNT(*) as extractions,
--   AVG(CASE WHEN extraction_status = 'correct' THEN 1.0 ELSE 0.0 END) as accuracy
-- FROM khatiyan_extractions
-- WHERE model_name = 'claude-3-5-sonnet-20241022'
-- GROUP BY prompt_version
-- ORDER BY prompt_version;

-- Search for specific district or khatiyan number (uses GIN index)
-- SELECT
--   ke.id,
--   kr.district, kr.tehsil, kr.village, kr.khatiyan_number,
--   ke.extraction_data,
--   ke.model_name,
--   ke.created_at
-- FROM khatiyan_extractions ke
-- JOIN khatiyan_records kr ON ke.khatiyan_record_id = kr.id
-- WHERE kr.district = 'Khordha'
--   OR kr.khatiyan_number = '1234';

-- Get all unique districts extracted
-- SELECT DISTINCT extraction_data->>'district' as district
-- FROM khatiyan_extractions
-- WHERE extraction_data->>'district' IS NOT NULL
-- ORDER BY district;

-- ============================================================================
-- Location Matching Audit Queries
-- ============================================================================

-- View all unresolved failures
-- SELECT * FROM unresolved_location_failures LIMIT 20;

-- Get matching statistics
-- SELECT * FROM location_matching_stats;

-- Find most common failure patterns
-- SELECT * FROM common_matching_failures LIMIT 20;

-- Find all failures for a specific village name
-- SELECT *
-- FROM location_matching_audit
-- WHERE location_type = 'village'
--   AND match_status = 'failed'
--   AND (native_value = 'ପାଟିଆ' OR english_value = 'Patia')
-- ORDER BY created_at DESC;

-- Mark a failure as resolved
-- UPDATE location_matching_audit
-- SET resolved = TRUE,
--     resolution_notes = 'Added village to master table',
--     resolved_by = 'admin',
--     resolved_at = NOW()
-- WHERE id = 123;

-- Get overall match rate
-- SELECT
--   COUNT(*) as total_attempts,
--   SUM(CASE WHEN match_status = 'success' THEN 1 ELSE 0 END) as successes,
--   ROUND(100.0 * SUM(CASE WHEN match_status = 'success' THEN 1 ELSE 0 END) / COUNT(*), 2) as success_rate
-- FROM location_matching_audit;

-- Find khatiyan records with ANY failed matches
-- SELECT DISTINCT kr.*
-- FROM khatiyan_records kr
-- JOIN location_matching_audit lma ON kr.id = lma.khatiyan_record_id
-- WHERE lma.match_status = 'failed'
--   AND lma.resolved = FALSE
-- ORDER BY kr.created_at DESC;

-- Analyze failures by date range
-- SELECT
--   DATE(created_at) as date,
--   location_type,
--   COUNT(*) as failure_count
-- FROM location_matching_audit
-- WHERE match_status = 'failed'
--   AND created_at >= NOW() - INTERVAL '7 days'
-- GROUP BY DATE(created_at), location_type
-- ORDER BY date DESC, failure_count DESC;

-- ============================================================================
-- Migration: Add HTML Parser Support (for existing databases)
-- ============================================================================
-- Run these ALTER statements to add HTML parser tracking to existing databases
--
-- These columns were added in the schema above, but if you're upgrading an
-- existing database, you'll need to run these manually:

-- Add extraction_method column
ALTER TABLE khatiyan_extractions ADD COLUMN IF NOT EXISTS extraction_method TEXT;
ALTER TABLE khatiyan_extractions ADD CONSTRAINT check_extraction_method
  CHECK (extraction_method IN ('html_parser', 'llm_fallback', 'llm_only') OR extraction_method IS NULL);

-- Add parser_confidence column
ALTER TABLE khatiyan_extractions ADD COLUMN IF NOT EXISTS parser_confidence TEXT;
ALTER TABLE khatiyan_extractions ADD CONSTRAINT check_parser_confidence
  CHECK (parser_confidence IN ('high', 'medium', 'low') OR parser_confidence IS NULL);

-- Add index for extraction_method
CREATE INDEX IF NOT EXISTS idx_extractions_method ON khatiyan_extractions(extraction_method);

-- ============================================================================
-- Monitoring Queries for HTML Parser Performance
-- ============================================================================

-- Check parser vs LLM usage distribution
-- SELECT
--   extraction_method,
--   COUNT(*) as count,
--   AVG(extraction_time_ms) as avg_time_ms,
--   MIN(extraction_time_ms) as min_time_ms,
--   MAX(extraction_time_ms) as max_time_ms
-- FROM khatiyan_extractions
-- WHERE created_at > NOW() - INTERVAL '7 days'
-- GROUP BY extraction_method;

-- Check parser confidence distribution
-- SELECT
--   parser_confidence,
--   COUNT(*) as count,
--   AVG(extraction_time_ms) as avg_time_ms
-- FROM khatiyan_extractions
-- WHERE extraction_method = 'html_parser'
--   AND created_at > NOW() - INTERVAL '7 days'
-- GROUP BY parser_confidence;

-- Find cases where parser fell back to LLM
-- SELECT
--   ke.id,
--   ke.extraction_method,
--   ke.parser_confidence,
--   ke.extraction_time_ms,
--   kr.district,
--   kr.tehsil,
--   kr.village,
--   kr.khatiyan_number,
--   ke.created_at
-- FROM khatiyan_extractions ke
-- JOIN khatiyan_records kr ON ke.khatiyan_record_id = kr.id
-- WHERE ke.extraction_method = 'llm_fallback'
-- ORDER BY ke.created_at DESC
-- LIMIT 20;

-- Compare extraction accuracy: HTML parser vs LLM
-- SELECT
--   extraction_method,
--   extraction_status,
--   COUNT(*) as count
-- FROM khatiyan_extractions
-- WHERE created_at > NOW() - INTERVAL '7 days'
--   AND extraction_status IN ('correct', 'wrong')
-- GROUP BY extraction_method, extraction_status
-- ORDER BY extraction_method, extraction_status;

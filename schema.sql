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
DROP VIEW IF EXISTS extraction_details CASCADE;
DROP VIEW IF EXISTS model_accuracy CASCADE;
DROP VIEW IF EXISTS latest_extractions CASCADE;

-- Drop triggers
DROP TRIGGER IF EXISTS update_khatiyan_extractions_updated_at ON khatiyan_extractions;
DROP TRIGGER IF EXISTS update_khatiyan_records_updated_at ON khatiyan_records;

-- Drop function
DROP FUNCTION IF EXISTS update_updated_at_column() CASCADE;

-- Drop tables (in reverse dependency order)
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

-- Index for looking up existing records by location
CREATE INDEX idx_khatiyan_records_location ON khatiyan_records(district, tehsil, village);
CREATE INDEX idx_khatiyan_records_created ON khatiyan_records(created_at DESC);

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
  model_provider TEXT NOT NULL,  -- 'anthropic', 'openai', 'mistral', 'google', etc.
  model_name TEXT NOT NULL,      -- 'claude-3-5-sonnet-20241022', 'gpt-4-turbo', etc.
  model_version TEXT,            -- Track model version updates

  -- Prompt tracking (for DSPy optimization)
  prompt_version TEXT DEFAULT 'v1',  -- Track DSPy signature versions
  prompt_config JSONB,           -- Store DSPy config/optimizer used

  -- Extracted data stored as JSON (extensible schema)
  -- This allows adding new fields without schema migrations
  -- Example structure: {"district": "...", "tehsil": "...", "owner_name": "...", ...}
  extraction_data JSONB NOT NULL,

  -- Quality and validation
  extraction_status TEXT CHECK (extraction_status IN ('pending', 'correct', 'wrong', 'needs_review')),
  confidence_score FLOAT CHECK (confidence_score >= 0 AND confidence_score <= 1),

  -- Performance metrics
  extraction_time_ms INTEGER,    -- Extraction duration in milliseconds
  tokens_used INTEGER,           -- API tokens consumed (for cost tracking)

  -- User feedback
  extraction_user_feedback TEXT, -- Optional free-form feedback/comments from users (especially when marking as 'wrong')
  feedback_timestamp TIMESTAMP WITH TIME ZONE,

  -- Summary storage (stored in same row as extraction)
  summary_html TEXT,                        -- Generated RoR summary HTML
  summary_generation_time_ms INTEGER,       -- Time to generate summary

  -- Summary quality and validation
  summarization_status TEXT CHECK (summarization_status IN ('pending', 'correct', 'wrong', 'needs_review')),
  summarization_user_feedback TEXT,         -- Optional feedback comments for summaries
  summary_feedback_timestamp TIMESTAMP WITH TIME ZONE,

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

-- Composite index for model comparison queries
CREATE INDEX idx_extractions_comparison ON khatiyan_extractions(khatiyan_record_id, model_name, extraction_status);

-- Index for summary queries (partial index - only rows with summaries)
CREATE INDEX idx_extractions_summary ON khatiyan_extractions(khatiyan_record_id, model_name) WHERE summary_html IS NOT NULL;

-- JSONB indexes for querying extracted data fields
-- GIN index for general JSONB queries
CREATE INDEX idx_extractions_data_gin ON khatiyan_extractions USING GIN (extraction_data);

-- Specific B-tree indexes for commonly queried fields (optional, for better performance on exact matches)
CREATE INDEX idx_extractions_district ON khatiyan_extractions ((extraction_data->>'district'));
CREATE INDEX idx_extractions_khatiyan_number ON khatiyan_extractions ((extraction_data->>'khatiyan_number'));

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

-- View: Model accuracy comparison
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
  AVG(extraction_time_ms) as avg_time_ms,
  AVG(tokens_used) as avg_tokens
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
  ke.confidence_score,
  ke.extraction_time_ms,
  ke.tokens_used,
  ke.created_at
FROM khatiyan_extractions ke
JOIN khatiyan_records kr ON ke.khatiyan_record_id = kr.id;

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

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
-- Table: khatiyan_records
-- ============================================================================
-- Stores unique Bhulekh webpage records with raw content
-- One record per unique URL/page visit

CREATE TABLE khatiyan_records (
  id BIGSERIAL PRIMARY KEY,

  -- Page identification
  url TEXT NOT NULL,
  title TEXT,

  -- Raw content (stored once for all extractions)
  raw_content TEXT,              -- Full text content from page
  raw_html TEXT,                 -- Original HTML (optional, for debugging)

  -- Metadata
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

  -- Ensure we don't duplicate the same page content
  CONSTRAINT unique_url_content UNIQUE(url, created_at)
);

-- Index for looking up existing records by URL
CREATE INDEX idx_khatiyan_records_url ON khatiyan_records(url);
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

  -- Extracted fields
  district TEXT,
  tehsil TEXT,
  village TEXT,
  khatiyan_number TEXT,

  -- Full extraction data (with any additional fields or confidence scores)
  extraction_data JSONB,

  -- Quality and validation
  extraction_status TEXT CHECK (extraction_status IN ('pending', 'correct', 'wrong', 'needs_review')),
  confidence_score FLOAT CHECK (confidence_score >= 0 AND confidence_score <= 1),

  -- Performance metrics
  extraction_time_ms INTEGER,    -- Extraction duration in milliseconds
  tokens_used INTEGER,           -- API tokens consumed (for cost tracking)

  -- User feedback
  user_feedback TEXT,            -- Optional text feedback from users
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

-- Composite index for model comparison queries
CREATE INDEX idx_extractions_comparison ON khatiyan_extractions(khatiyan_record_id, model_name, extraction_status);

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
  kr.url,
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
--   kr.url,
--   ke1.district as claude_district,
--   ke2.district as gpt4_district,
--   ke1.extraction_status as claude_status,
--   ke2.extraction_status as gpt4_status
-- FROM khatiyan_records kr
-- JOIN khatiyan_extractions ke1 ON kr.id = ke1.khatiyan_record_id
--   AND ke1.model_name LIKE 'claude%'
-- LEFT JOIN khatiyan_extractions ke2 ON kr.id = ke2.khatiyan_record_id
--   AND ke2.model_name LIKE 'gpt%'
-- WHERE ke1.district != ke2.district;

-- Find records needing review
-- SELECT * FROM khatiyan_extractions
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

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
-- Function and Trigger: Auto-populate Location IDs in khatiyan_records
-- ============================================================================
-- Automatically populates district_id, tehsil_id, and village_id columns
-- by matching text names against master tables (villages, tahasils)
--
-- Business Logic:
-- 1. Match village name → get villages.id and villages.district_id
-- 2. Match tehsil name → get tahasils.id
-- 3. Validate consistency between matched records
--
-- Matching Strategy (tries in this order until a match is found):
-- For each location (village/tehsil):
--   1. Try native_village/native_tehsil against master.native_name
--   2. Try native_village/native_tehsil against master.english_name
--   3. Try village/tehsil against master.native_name
--   4. Try village/tehsil against master.english_name
-- All matches are case-insensitive with trimmed whitespace
-- Use LIMIT 1 if multiple matches (takes first)

CREATE OR REPLACE FUNCTION populate_khatiyan_location_ids()
RETURNS TRIGGER AS $$
DECLARE
  matched_village_id bigint;
  matched_village_district_id bigint;
  matched_village_tahasil_id bigint;
  matched_tehsil_id bigint;
  matched_tehsil_district_id bigint;
BEGIN
  -- -------------------------------------------------------------------------
  -- Step 1: Match VILLAGE name against villages table
  -- Try native column first, then fall back to English column
  -- -------------------------------------------------------------------------

  -- Try matching native_village (if populated)
  IF NEW.native_village IS NOT NULL AND TRIM(NEW.native_village) != '' THEN
    -- Try native_village against villages.native_name
    SELECT id, district_id, tahasil_id
    INTO matched_village_id, matched_village_district_id, matched_village_tahasil_id
    FROM villages
    WHERE LOWER(TRIM(native_name)) = LOWER(TRIM(NEW.native_village))
    LIMIT 1;

    -- If no match, try native_village against villages.english_name
    IF matched_village_id IS NULL THEN
      SELECT id, district_id, tahasil_id
      INTO matched_village_id, matched_village_district_id, matched_village_tahasil_id
      FROM villages
      WHERE LOWER(TRIM(english_name)) = LOWER(TRIM(NEW.native_village))
      LIMIT 1;
    END IF;
  END IF;

  -- If still no match, try the English village column
  IF matched_village_id IS NULL AND NEW.village IS NOT NULL AND TRIM(NEW.village) != '' THEN
    -- Try village against villages.native_name
    SELECT id, district_id, tahasil_id
    INTO matched_village_id, matched_village_district_id, matched_village_tahasil_id
    FROM villages
    WHERE LOWER(TRIM(native_name)) = LOWER(TRIM(NEW.village))
    LIMIT 1;

    -- If no match, try village against villages.english_name
    IF matched_village_id IS NULL THEN
      SELECT id, district_id, tahasil_id
      INTO matched_village_id, matched_village_district_id, matched_village_tahasil_id
      FROM villages
      WHERE LOWER(TRIM(english_name)) = LOWER(TRIM(NEW.village))
      LIMIT 1;
    END IF;
  END IF;

  -- Populate the IDs from matched village
  IF matched_village_id IS NOT NULL THEN
    NEW.village_id := matched_village_id;
    NEW.district_id := matched_village_district_id;

    RAISE INFO 'Matched village (native: "%, english: "%") → village_id=%, district_id=%',
               NEW.native_village, NEW.village, matched_village_id, matched_village_district_id;
  ELSE
    RAISE WARNING 'No match found for village (native: "%, english: "%")',
                  NEW.native_village, NEW.village;
  END IF;

  -- -------------------------------------------------------------------------
  -- Step 2: Match TEHSIL name against tahasils table
  -- Try native column first, then fall back to English column
  -- -------------------------------------------------------------------------

  -- Try matching native_tehsil (if populated)
  IF NEW.native_tehsil IS NOT NULL AND TRIM(NEW.native_tehsil) != '' THEN
    -- Try native_tehsil against tahasils.native_name
    SELECT id, district_id
    INTO matched_tehsil_id, matched_tehsil_district_id
    FROM tahasils
    WHERE LOWER(TRIM(native_name)) = LOWER(TRIM(NEW.native_tehsil))
    LIMIT 1;

    -- If no match, try native_tehsil against tahasils.english_name
    IF matched_tehsil_id IS NULL THEN
      SELECT id, district_id
      INTO matched_tehsil_id, matched_tehsil_district_id
      FROM tahasils
      WHERE LOWER(TRIM(english_name)) = LOWER(TRIM(NEW.native_tehsil))
      LIMIT 1;
    END IF;
  END IF;

  -- If still no match, try the English tehsil column
  IF matched_tehsil_id IS NULL AND NEW.tehsil IS NOT NULL AND TRIM(NEW.tehsil) != '' THEN
    -- Try tehsil against tahasils.native_name
    SELECT id, district_id
    INTO matched_tehsil_id, matched_tehsil_district_id
    FROM tahasils
    WHERE LOWER(TRIM(native_name)) = LOWER(TRIM(NEW.tehsil))
    LIMIT 1;

    -- If no match, try tehsil against tahasils.english_name
    IF matched_tehsil_id IS NULL THEN
      SELECT id, district_id
      INTO matched_tehsil_id, matched_tehsil_district_id
      FROM tahasils
      WHERE LOWER(TRIM(english_name)) = LOWER(TRIM(NEW.tehsil))
      LIMIT 1;
    END IF;
  END IF;

  -- Populate tehsil_id
  IF matched_tehsil_id IS NOT NULL THEN
    NEW.tehsil_id := matched_tehsil_id;

    RAISE INFO 'Matched tehsil (native: "%, english: "%") → tehsil_id=%',
               NEW.native_tehsil, NEW.tehsil, matched_tehsil_id;
  ELSE
    RAISE WARNING 'No match found for tehsil (native: "%, english: "%")',
                  NEW.native_tehsil, NEW.tehsil;
  END IF;

  -- -------------------------------------------------------------------------
  -- Step 3: Data Consistency Validation
  -- -------------------------------------------------------------------------

  -- Validate: village.tahasil_id should match matched tehsil.id
  IF matched_village_tahasil_id IS NOT NULL AND matched_tehsil_id IS NOT NULL THEN
    IF matched_village_tahasil_id != matched_tehsil_id THEN
      RAISE WARNING 'Data inconsistency detected: village "%" has tahasil_id=% but matched tehsil "%" has id=%',
                    NEW.village, matched_village_tahasil_id, NEW.tehsil, matched_tehsil_id;
    END IF;
  END IF;

  -- Validate: village.district_id should match tehsil.district_id
  IF matched_village_district_id IS NOT NULL AND matched_tehsil_district_id IS NOT NULL THEN
    IF matched_village_district_id != matched_tehsil_district_id THEN
      RAISE WARNING 'Data inconsistency detected: village "%" has district_id=% but matched tehsil "%" has district_id=%',
                    NEW.village, matched_village_district_id, NEW.tehsil, matched_tehsil_district_id;
    END IF;
  END IF;

  -- Validate: district text matches the resolved district_id
  -- (This requires querying the districts table - optional validation)
  IF NEW.district IS NOT NULL AND NEW.district_id IS NOT NULL THEN
    DECLARE
      district_name_check TEXT;
    BEGIN
      SELECT native_name INTO district_name_check
      FROM districts
      WHERE id = NEW.district_id
      LIMIT 1;

      IF LOWER(TRIM(district_name_check)) != LOWER(TRIM(NEW.district)) THEN
        -- Also try english_name
        SELECT english_name INTO district_name_check
        FROM districts
        WHERE id = NEW.district_id
        LIMIT 1;

        IF district_name_check IS NULL OR LOWER(TRIM(district_name_check)) != LOWER(TRIM(NEW.district)) THEN
          RAISE WARNING 'District text "%" does not match resolved district_id=% (expected "%")',
                        NEW.district, NEW.district_id, district_name_check;
        END IF;
      END IF;
    EXCEPTION
      WHEN undefined_table THEN
        -- districts table doesn't exist, skip validation
        NULL;
    END;
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

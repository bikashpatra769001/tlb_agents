-- Migration: Add page_contexts table for Lambda persistence
-- Run this if you already have existing khatiyan tables and just want to add page_contexts

-- Drop table if exists (for clean reinstall)
DROP TABLE IF EXISTS page_contexts CASCADE;

-- Create page_contexts table
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

-- Verify table was created
SELECT
    'page_contexts table created successfully!' as status,
    COUNT(*) as row_count
FROM page_contexts;

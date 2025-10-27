# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Chrome extension with a FastAPI backend that enables chat-based interaction with Bhulekh website content (https://bhulekh.ori.nic.in). The system extracts webpage content and uses Claude Sonnet (Anthropic) to answer questions about it.

## Deployment

**Current Status: ✅ Deployed to AWS Lambda (Production)**

The application is deployed as a serverless Lambda function using Docker containers:
- **Lambda Function**: `bhulekha-extension-api` (us-east-1)
- **API Endpoint**: `https://9tzh9wd092.execute-api.us-east-1.amazonaws.com`
- **Container**: 2048MB memory, 300s timeout, stored in Amazon ECR
- **Extension ID**: `hknfgjmgpcdehabepbgifofnglkiihgb` (production package)

See **[DEPLOYMENT.md](DEPLOYMENT.md)** for complete deployment guide including:
- Lambda Container Image deployment (Option 2 - currently in use)
- Docker containerization with automated deployment scripts
- API Gateway HTTP API configuration
- Environment variable management (DSPY_CACHEDIR, CORS, etc.)
- Cost estimates (~$3.71/month base, ~$18/month with beta testing)

For beta testing setup, see **[BETA_TESTING_GUIDE.md](BETA_TESTING_GUIDE.md)** and **[DISTRIBUTION_README.md](DISTRIBUTION_README.md)**

## Architecture

### Two-Component System

1. **FastAPI Backend** (`api_server.py`)
   - **Local Dev**: Runs on `localhost:8000` with uvicorn
   - **Production**: Deployed as AWS Lambda function via Mangum adapter
   - Uses Anthropic Claude Sonnet 3.5 (`claude-3-5-sonnet-20241022`) for content analysis
   - Stores page contexts in **Supabase** (persistent, Lambda-compatible)
   - URL-restricted to only allow Bhulekh websites for security
   - Environment-aware CORS (development: all origins, production: specific extension ID)
   - Contains `SummarizationAgent` class with fallback responses when API key is unavailable

2. **Chrome Extension** (`chrome-extension/`)
   - Manifest V3 Chrome extension written in TypeScript
   - Chat interface in popup window (`popup.html`, compiled from `src/popup.ts`)
   - Content script (compiled from `src/content.ts`) for Bhulekh page extraction
   - **Tester Identification**: Chrome Storage API for persistent tester IDs with first-time modal setup
   - **Beta Testing Ready**: All API requests include `X-Tester-ID` header for tracking
   - Restricted to `https://bhulekh.ori.nic.in/*` URLs
   - TypeScript source in `src/`, compiled JavaScript in `dist/`
   - Production package: `bhulekha-extension-v1.0.zip` (Extension ID: `hknfgjmgpcdehabepbgifofnglkiihgb`)

### Key Components

- **HTML Parser** (`html_parser.py`): **NEW** Deterministic parser for Bhulekh RoR HTML
  - **Primary extraction method** for `/explain` endpoint
  - Parses structured HTML to extract location, owner, plot, and metadata
  - Supports bilingual extraction (Odia and English)
  - Confidence scoring: "high", "medium", "low"
  - **60x faster** than LLM extraction (~50ms vs ~3000ms)
  - **Zero cost** (no API calls)
  - **Automatic fallback** to LLM when confidence < "high"

- **DSPy Signatures** (api_server.py:66-100): Programmable prompts for extraction, explanation, Q&A
  - `ExtractKhatiyan`: Extract district, tehsil, village, khatiyan_number (LLM fallback)
  - `ExplainContent`: Generate simple explanations
  - `AnswerQuestion`: Answer user questions
  - `SummarizeContent`: Create summaries
  - `SummarizeRoR`: Generate RoR summaries with risk assessment (still uses LLM)

- **SummarizationAgent** (api_server.py:104-216): Handles AI operations using DSPy (used as fallback)

- **Supabase Storage Functions**:
  - `get_or_create_khatiyan_record()`: Creates/retrieves page record
  - `store_khatiyan_extraction()`: Stores extraction with metadata (tracks method: html_parser vs llm_fallback)
  - `store_page_context()`: Stores page content for Lambda persistence
  - `get_page_context()`: Retrieves stored page content for chat context

- **Tester Tracking**: `get_tester_id(request)` extracts `X-Tester-ID` header and logs all requests
- **Lambda Handler**: Mangum adapter for AWS Lambda compatibility (api_server.py:~940)
- **URL Whitelist**: Security restriction to Bhulekh URLs only

### Database Schema

The application uses a **two-table design** for extensibility:

1. **khatiyan_records**: Stores raw page content once
   - Deduplication by (district, tehsil, village, khatiyan_number) combination
   - Khatiyan numbers are only unique within a specific district/tehsil/village
   - One record per unique khatiyan (reused if same khatiyan viewed multiple times)
   - URL field removed as it doesn't change across different records

2. **khatiyan_extractions**: Stores AI model outputs (and HTML parser results)
   - Multiple extractions per record (different models/prompts)
   - Tracks: model provider, name, version, prompt version
   - **NEW**: `extraction_method` ("html_parser" or "llm_fallback")
   - **NEW**: `parser_confidence` ("high", "medium", "low")
   - Performance metrics: time, tokens
   - Quality tracking: extraction_status (pending/correct/wrong)

This design enables:
- Multi-model comparison (Claude vs GPT-4 vs Mistral vs HTML Parser)
- A/B testing different prompts
- DSPy optimization tracking
- Cost and performance analysis
- **Monitoring parser success rate and fallback patterns**

## HTML Parser for Data Extraction

**NEW**: The `/explain` endpoint now uses a deterministic HTML parser as the primary extraction method.

### Why HTML Parser?

- **Performance**: 60x faster (~50ms vs ~3000ms for LLM)
- **Cost**: $0 per extraction (vs ~$0.02 per LLM call)
- **Reliability**: 100% deterministic, no API rate limits
- **Accuracy**: Extracts exact values from structured HTML

### How It Works

1. **Primary Method**: BeautifulSoup4-based parser (`html_parser.py`)
   - Parses Bhulekha RoR HTML structure
   - Extracts bilingual fields (Odia and English)
   - Aggregates plot data, calculates totals
   - Extracts metadata (dates, police station, revenue)

2. **Confidence Scoring**: Based on field completeness
   - **High (≥95%)**: Use parser result directly
   - **Medium (70-94%)**: Fall back to LLM
   - **Low (<70%)**: Fall back to LLM

3. **Automatic Fallback**: If parser confidence < "high", system automatically uses LLM extraction

### Extracted Fields

**Location** (bilingual: Odia + English):
- District, Tehsil, Village, Khatiyan Number

**Owner Information**:
- Primary owner name, father's name, caste
- Other co-owners (if multiple)

**Plot Information**:
- Total plots, plot numbers, total area (hectares)
- Land type, plot-specific notes

**Metadata** (special_comments):
- Final publication date, rent fixation date
- Police station, tahasil number, land revenue

### Monitoring Parser Performance

Check extraction method distribution:
```sql
SELECT
    extraction_method,
    COUNT(*) as count,
    AVG(extraction_time_ms) as avg_time_ms
FROM khatiyan_extractions
WHERE created_at > NOW() - INTERVAL '7 days'
GROUP BY extraction_method;
```

Find fallback cases:
```sql
SELECT * FROM khatiyan_extractions
WHERE extraction_method = 'llm_fallback'
ORDER BY created_at DESC
LIMIT 20;
```

Compare accuracy:
```sql
SELECT
    extraction_method,
    extraction_status,
    COUNT(*) as count
FROM khatiyan_extractions
WHERE extraction_status IN ('correct', 'wrong')
GROUP BY extraction_method, extraction_status;
```

### Testing

Run parser unit tests:
```bash
python test_html_parser.py
```

Tests validate:
- Field extraction accuracy
- Bilingual parsing (Odia/English)
- Plot data aggregation
- Confidence scoring
- Fallback behavior

**Test File**: `test_html_parser.py`
**Sample Data**: `sample_bhulekha.html`

## Development Commands

### Python API

```bash
# Install all dependencies
uv sync

# Start the API server (required for extension to work)
python api_server.py

# Add new dependencies
uv add <package-name>
```

### Environment Setup

The API requires multiple environment variables:

```bash
# Create .env file in project root with:

# Required for AI features
ANTHROPIC_API_KEY=your_anthropic_key_here

# Required for data storage (optional but recommended)
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your_supabase_anon_key
```

**Setting up Supabase:**
1. Create account at https://supabase.com
2. Create new project
3. Go to Project Settings → API
4. Copy `URL` and `anon/public` key
5. Run the SQL schema from `schema.sql`:
   - Open Supabase SQL Editor
   - Copy entire contents of `schema.sql`
   - Execute to create tables, indexes, views, and triggers

**Schema Overview:**
- `khatiyan_records`: Stores unique page content (one per unique district/tehsil/village/khatiyan_number)
- `khatiyan_extractions`: Stores AI model extractions (many per record)
- `prompt_optimizations`: Tracks DSPy optimization experiments (optional)
- Views for model comparison and accuracy tracking

**Without keys:**
- `ANTHROPIC_API_KEY` missing: Fallback responses (limited functionality)
- `SUPABASE_URL/KEY` missing: Data extraction still works, but not stored

### Chrome Extension Development

The extension is written in TypeScript and must be compiled before use:

```bash
cd chrome-extension

# Install dependencies (first time only)
npm install

# Build TypeScript to JavaScript
npm run build

# Watch mode for development (auto-recompile on changes)
npm run watch

# Clean build artifacts
npm run clean
```

**Loading the extension:**
1. Build the extension first: `cd chrome-extension && npm run build`
2. Chrome → `chrome://extensions/` → Enable Developer Mode → Load Unpacked → Select `chrome-extension/` folder
3. After TypeScript changes: Run `npm run build` (or use `npm run watch`), then click reload icon on extension card
4. After API changes: Restart `python api_server.py`

**TypeScript structure:**
- Source files: `chrome-extension/src/*.ts`
- Compiled output: `chrome-extension/dist/*.js`
- Configuration: `tsconfig.json`
- Chrome API types: `@types/chrome` package

## Testing Workflow

1. Start API server: `python api_server.py`
2. Navigate to https://bhulekh.ori.nic.in/SRoRFront_Uni.aspx or CRoRFront_Uni.aspx
3. Click extension icon
4. Click "📄 Load Page Content" button
5. Ask questions in chat interface

## API Endpoints

- `POST /load-content`: Store webpage content for chat context
- `POST /chat`: Process chat queries about loaded content
- `POST /process-content`: Legacy endpoint (backward compatibility)
- `GET /health`: Health check

## Key Constraints

- **URL Restriction**: Only works with URLs starting with:
  - `https://bhulekh.ori.nic.in/SRoRFront_Uni.aspx`
  - `https://bhulekh.ori.nic.in/CRoRFront_Uni.aspx`
- **Python Version**: Requires Python 3.12+ (specified in `.python-version`)
- **Package Manager**: Use `uv` exclusively (not pip)
- **CORS**: Enabled for all origins in development (needs tightening for production)

## Dependencies

- `fastapi`: Web framework
- `uvicorn`: ASGI server
- `anthropic`: Claude API client
- `dspy-ai`: Programmable prompting framework
- `supabase`: Supabase client for data storage
- `python-dotenv`: Environment variable management
- `pydantic`: Data validation (via FastAPI)

## DSPy Prompt Engineering

This project uses DSPy for programmable prompting, which enables:

1. **Type-Safe Prompts**: Defined as signatures with input/output fields
2. **Easy Iteration**: Modify prompts by changing signature descriptions
3. **Composability**: Chain multiple prompts together
4. **Future Optimization**: Use feedback data (extraction_status) to optimize prompts

**Adding New Prompts:**
```python
# 1. Define signature
class NewTask(dspy.Signature):
    """Description of what this prompt does"""
    input_field: str = dspy.InputField(desc="Input description")
    output_field: str = dspy.OutputField(desc="Output description")

# 2. Add to SummarizationAgent.__init__
self.new_task = dspy.ChainOfThought(NewTask)

# 3. Use it
result = self.new_task(input_field="...")
```

**Optimizing Prompts Later:**
```python
# Collect feedback from extraction_status column
# Use DSPy optimizers to improve extraction accuracy
optimizer = dspy.BootstrapFewShot(metric=accuracy)
optimized = optimizer.compile(extractor, trainset=feedback_data)
```

**Tracking Prompt Versions:**
- Increment `prompt_version` in `/explain` endpoint when optimizing
- Each version stored separately in `khatiyan_extractions`
- Compare accuracy across versions using `model_accuracy` view

## Multi-Model Support

The schema supports multiple AI models:

**Adding a New Model:**
```python
# In /explain endpoint, add another extraction:
gpt4_data = await gpt4_agent.extract_khatiyan_details(...)

await store_khatiyan_extraction(
    khatiyan_record_id=record_id,
    extraction_data=gpt4_data,
    model_provider="openai",
    model_name="gpt-4-turbo",
    prompt_version="v1"
)
```

**Comparing Models:**
```sql
-- Query the model_accuracy view
SELECT * FROM model_accuracy ORDER BY accuracy_percentage DESC;

-- Find disagreements between models
SELECT kr.url, ke1.district as claude_dist, ke2.district as gpt4_dist
FROM khatiyan_records kr
JOIN khatiyan_extractions ke1 ON kr.id = ke1.khatiyan_record_id
  AND ke1.model_name = 'claude-3-5-sonnet-20241022'
JOIN khatiyan_extractions ke2 ON kr.id = ke2.khatiyan_record_id
  AND ke2.model_name = 'gpt-4-turbo'
WHERE ke1.district != ke2.district;
```

## Production Considerations

Current implementation is NOT production-ready:
- In-memory storage (`page_contexts`) - for chat context only, needs Redis/DB for production
- CORS allows all origins - needs restriction to extension origin
- No authentication/rate limiting on API endpoints
- No logging infrastructure
- Supabase RLS (Row Level Security) not configured

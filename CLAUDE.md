# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Chrome extension with a FastAPI backend that enables chat-based interaction with Bhulekh website content (https://bhulekh.ori.nic.in). The system extracts webpage content and uses Claude Sonnet (Anthropic) to answer questions about it.

## Architecture

### Two-Component System

1. **FastAPI Backend** (`api_server.py`)
   - Hosts chat API endpoints on `localhost:8000`
   - Uses Anthropic Claude Sonnet 3.5 (`claude-3-5-sonnet-20241022`) for content analysis
   - Stores page contexts in-memory (not persistent)
   - URL-restricted to only allow Bhulekh websites for security
   - Contains `SummarizationAgent` class with fallback responses when API key is unavailable

2. **Chrome Extension** (`chrome-extension/`)
   - Manifest V3 Chrome extension
   - Chat interface in popup window (`popup.html`, `popup.js`)
   - Content script (`content.js`) for Bhulekh page extraction
   - Restricted to `https://bhulekh.ori.nic.in/*` URLs

### Key Components

- **DSPy Signatures** (api_server.py:66-100): Programmable prompts for extraction, explanation, Q&A
  - `ExtractKhatiyan`: Extract district, tehsil, village, khatiyan_number
  - `ExplainContent`: Generate simple explanations
  - `AnswerQuestion`: Answer user questions
  - `SummarizeContent`: Create summaries
- **SummarizationAgent** (api_server.py:104-216): Handles all AI operations using DSPy
- **Supabase Storage** (api_server.py:223-247): Stores extracted Khatiyan data
- **URL Whitelist** (api_server.py:249-256): Security restriction to Bhulekh URLs only
- **In-memory Storage** (api_server.py:27): `page_contexts` dict - for chat context only

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
5. Create table `khatiyan_records` with schema:
   ```sql
   CREATE TABLE khatiyan_records (
     id BIGSERIAL PRIMARY KEY,
     district TEXT,
     tehsil TEXT,
     village TEXT,
     khatiyan_number TEXT,
     claude_extract JSONB,
     extraction_status TEXT CHECK (extraction_status IN ('correct', 'wrong')),
     url TEXT,
     title TEXT,
     created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
   );
   ```

**Without keys:**
- `ANTHROPIC_API_KEY` missing: Fallback responses (limited functionality)
- `SUPABASE_URL/KEY` missing: Data extraction still works, but not stored

### Chrome Extension Development

1. Load extension: Chrome → `chrome://extensions/` → Enable Developer Mode → Load Unpacked → Select `chrome-extension/` folder
2. After code changes to extension: Click reload icon on extension card
3. After API changes: Restart `python api_server.py`

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

## Production Considerations

Current implementation is NOT production-ready:
- In-memory storage (`page_contexts`) - for chat context only, needs Redis/DB for production
- CORS allows all origins - needs restriction to extension origin
- No authentication/rate limiting on API endpoints
- No logging infrastructure
- Supabase RLS (Row Level Security) not configured

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

- **SummarizationAgent** (api_server.py:41-146): Handles Claude API calls with fallback logic
- **URL Whitelist** (api_server.py:149-156): Security restriction to Bhulekh URLs only
- **In-memory Storage** (api_server.py:27): `page_contexts` dict - not production-ready

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

The API requires `ANTHROPIC_API_KEY` environment variable:
- Create `.env` file in project root
- Add: `ANTHROPIC_API_KEY=your_key_here`
- Without this key, fallback responses are used (limited functionality)

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
- `python-dotenv`: Environment variable management
- `pydantic`: Data validation (via FastAPI)

## Production Considerations

Current implementation is NOT production-ready:
- In-memory storage (`page_contexts`) - needs database
- CORS allows all origins - needs restriction
- No authentication/rate limiting
- No logging infrastructure

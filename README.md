# Chrome Extension Chat Interface + Python API

A Chrome extension with a chat interface that reads webpage content and allows users to ask questions about it through a Python FastAPI backend.

## Setup Instructions

### 1. Python API Setup

```bash
# Install dependencies
uv sync

# Start the API server
python api_server.py
```

The API will be available at `http://localhost:8000`

### 2. Chrome Extension Setup

1. Open Chrome and go to `chrome://extensions/`
2. Enable "Developer mode" (toggle in top right)
3. Click "Load unpacked"
4. Select the `chrome-extension` folder from this project
5. The extension should now appear in your extensions list

### 3. Usage

1. Make sure the Python API server is running (`python api_server.py`)
2. Navigate to any webpage
3. Click the extension icon in Chrome's toolbar
4. Click "📄 Load Page Content" to extract the webpage content
5. Once loaded, use the chat interface to ask questions about the page

## Chat Features

Ask questions like:
- "Summarize this page"
- "How many words are on this page?"
- "What's the title?"
- "Search for [term]"
- "Is this a long page?"

## API Endpoints

- `GET /` - Root endpoint with welcome message
- `GET /health` - Health check endpoint
- `POST /load-content` - Load webpage content for chat context
- `POST /chat` - Process chat queries about loaded content
- `POST /process-content` - Legacy endpoint (backward compatibility)

## Extension Features

- **Chat Interface**: Clean chat UI with user/bot message bubbles
- **Content Loading**: Extracts both text and HTML content from webpages
- **Real-time Chat**: Ask questions and get instant responses
- **Keyboard Shortcuts**: Press Enter to send, Shift+Enter for new lines
- **Auto-scroll**: Chat automatically scrolls to show latest messages
- **Status Indicators**: Clear feedback on loading and error states

## Customization

Enhance the chat responses in `api_server.py` by:
- Adding more keyword patterns in the `chat_with_content` function
- Integrating with AI/LLM services (OpenAI, Anthropic, etc.)
- Adding more sophisticated content analysis

## Development

- Python API uses FastAPI with CORS enabled for Chrome extension
- Extension uses Manifest V3 format with modern chat UI
- Content is extracted using Chrome's scripting API
- In-memory storage for page contexts (use database for production)
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
import os
from anthropic import Anthropic
from typing import Optional
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()
from dotenv import load_dotenv
load_dotenv()

app = FastAPI(title="Webpage Content Chat API")

# Enable CORS for Chrome extension
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your extension's origin
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Store page content in memory (in production, use a proper database)
page_contexts = {}

# Initialize Anthropic client
anthropic_client = None
try:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if api_key:
        anthropic_client = Anthropic(api_key=api_key)
        print("✅ Anthropic Claude initialized successfully")
    else:
        print("⚠️  ANTHROPIC_API_KEY not found. AI features will be limited.")
except Exception as e:
    print(f"❌ Error initializing Anthropic: {e}")

class SummarizationAgent:
    """Agent for summarizing webpage content using Claude Sonnet"""
    
    def __init__(self, client: Optional[Anthropic] = None):
        self.client = client
        self.model = "claude-3-5-sonnet-20241022"
    
    async def summarize_content(self, content: str, title: str = "") -> str:
        """Summarize webpage content using Claude Sonnet"""
        if not self.client:
            return self._fallback_summary(content, title)
        
        try:
            prompt = f"""Please provide a clear and concise summary of the following webpage content.

Title: {title}

Content:
{content}

Please provide:
1. A brief overview of what this page is about
2. Key information or main points
3. Any important details that users should know

Keep the summary informative but concise."""

            response = self.client.messages.create(
                model=self.model,
                max_tokens=1000,
                temperature=0.3,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            
            return response.content[0].text
            
        except Exception as e:
            print(f"Error with Claude API: {e}")
            return self._fallback_summary(content, title)
    
    async def answer_question(self, content: str, title: str, question: str) -> str:
        """Answer questions about webpage content using Claude Sonnet"""
        if not self.client:
            return self._fallback_answer(content, question)
        
        try:
            prompt = f"""Based on the following webpage content, please answer the user's question accurately and helpfully.

Webpage Title: {title}

Webpage Content:
{content}

User Question: {question}

Please provide a clear, accurate answer based only on the information available in the webpage content. If the information isn't available in the content, please say so."""

            response = self.client.messages.create(
                model=self.model,
                max_tokens=1000,
                temperature=0.3,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            
            return response.content[0].text
            
        except Exception as e:
            print(f"Error with Claude API: {e}")
            return self._fallback_answer(content, question)
    
    def _fallback_summary(self, content: str, title: str) -> str:
        """Fallback summary when Claude is not available"""
        word_count = len(content.split())
        preview = content[:400] + "..." if len(content) > 400 else content
        
        return f"""**Summary of: {title}**

This page contains {word_count} words. Here's a preview of the content:

{preview}

*Note: AI-powered summarization is not available. Please set ANTHROPIC_API_KEY environment variable for enhanced summaries.*"""
    
    def _fallback_answer(self, content: str, question: str) -> str:
        """Fallback answer when Claude is not available"""
        question_lower = question.lower()
        
        if "summary" in question_lower or "summarize" in question_lower:
            return self._fallback_summary(content, "")
        elif "word count" in question_lower or "how many words" in question_lower:
            return f"This page contains {len(content.split())} words."
        elif "search" in question_lower or "find" in question_lower:
            search_term = question.replace("search", "").replace("find", "").strip()
            if search_term and search_term.lower() in content.lower():
                return f"Yes, I found '{search_term}' in the page content."
            else:
                return f"I couldn't find '{search_term}' in the page content."
        else:
            return "I can help you with basic questions about this page. For advanced AI-powered responses, please set the ANTHROPIC_API_KEY environment variable."

# Initialize the summarization agent
summarization_agent = SummarizationAgent(anthropic_client)

# Define allowed URLs
ALLOWED_URLS = [
    "https://bhulekh.ori.nic.in/SRoRFront_Uni.aspx",
    "https://bhulekh.ori.nic.in/CRoRFront_Uni.aspx"
]

def is_url_allowed(url: str) -> bool:
    """Check if the URL is in the allowed list"""
    return any(url.startswith(allowed_url) for allowed_url in ALLOWED_URLS)

class WebpageContent(BaseModel):
    url: str
    title: str
    content: dict  # Contains 'text' and 'html' fields

class ChatQuery(BaseModel):
    query: str
    url: str
    title: str

@app.post("/load-content")
async def load_content(webpage: WebpageContent):
    """
    Load webpage content and store it for chat context
    """
    try:
        # Validate URL - only allow Bhulekh website
        if not is_url_allowed(webpage.url):
            allowed_urls_str = ", ".join(ALLOWED_URLS)
            raise HTTPException(
                status_code=403, 
                detail=f"Access denied. This service only works with these URLs: {allowed_urls_str}"
            )
        
        # Extract content
        text_content = webpage.content.get('text', '')
        html_content = webpage.content.get('html', '')
        
        # Store content for this URL
        page_contexts[webpage.url] = {
            "title": webpage.title,
            "text": text_content,
            "html": html_content,
            "word_count": len(text_content.split()),
            "char_count": len(text_content)
        }
        
        print(f"Loaded content from: {webpage.url}")
        print(f"Title: {webpage.title}")
        print(f"Word count: {len(text_content.split())}")
        
        return {
            "status": "success",
            "message": "Content loaded successfully",
            "word_count": len(text_content.split())
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error loading content: {str(e)}")

@app.post("/chat")
async def chat_with_content(chat: ChatQuery):
    """
    Process chat queries about the loaded webpage content
    """
    try:
        # Validate URL - only allow Bhulekh website
        if not is_url_allowed(chat.url):
            allowed_urls_str = ", ".join(ALLOWED_URLS)
            raise HTTPException(
                status_code=403, 
                detail=f"Access denied. This service only works with these URLs: {allowed_urls_str}"
            )
        
        # Get stored content for this URL
        if chat.url not in page_contexts:
            raise HTTPException(status_code=404, detail="Page content not loaded. Please load the page first.")
        
        page_data = page_contexts[chat.url]
        text_content = page_data["text"]
        
        # Use AI-powered responses with Claude Sonnet
        query_lower = chat.query.lower()
        
        # Check for summary requests
        if "summary" in query_lower or "summarize" in query_lower:
            response = await summarization_agent.summarize_content(text_content, page_data['title'])
        else:
            # Use Claude to answer general questions about the content
            response = await summarization_agent.answer_question(
                text_content, 
                page_data['title'], 
                chat.query
            )
        
        print(f"Chat query from {chat.url}: {chat.query}")
        
        return {
            "response": response,
            "query": chat.query,
            "url": chat.url
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing chat: {str(e)}")

@app.post("/process-content")
async def process_content(webpage: WebpageContent):
    """
    Legacy endpoint - process webpage content (kept for backward compatibility)
    """
    return await load_content(webpage)

@app.get("/")
async def root():
    return {"message": "Webpage Content Chat API is running"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
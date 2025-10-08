from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
import os
from anthropic import Anthropic
from typing import Optional
from dotenv import load_dotenv
import dspy
from supabase import create_client, Client

# Load environment variables from .env file
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

# Initialize DSPy with Claude
try:
    if api_key:
        # Configure DSPy to use Claude via Anthropic
        claude_lm = dspy.LM('anthropic/claude-3-5-sonnet-20241022', api_key=api_key)
        dspy.configure(lm=claude_lm)
        print("✅ DSPy configured with Claude Sonnet")
    else:
        print("⚠️  DSPy not configured - ANTHROPIC_API_KEY missing")
except Exception as e:
    print(f"❌ Error initializing DSPy: {e}")

# Initialize Supabase client
supabase_client: Optional[Client] = None
try:
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_KEY")
    if supabase_url and supabase_key:
        supabase_client = create_client(supabase_url, supabase_key)
        print("✅ Supabase client initialized successfully")
    else:
        print("⚠️  SUPABASE_URL or SUPABASE_KEY not found. Data storage will be disabled.")
except Exception as e:
    print(f"❌ Error initializing Supabase: {e}")

# ==================== DSPy Signatures ====================

class ExtractKhatiyan(dspy.Signature):
    """Extract structured Khatiyan land record details from Bhulekha webpage content.
    Look for district, tehsil, village, and khatiyan number in both English and Hindi text."""

    content: str = dspy.InputField(desc="The webpage text content")
    title: str = dspy.InputField(desc="The webpage title")
    district: str = dspy.OutputField(desc="The district (जिला) name")
    tehsil: str = dspy.OutputField(desc="The tehsil/block (तहसील) name")
    village: str = dspy.OutputField(desc="The village (गाँव) name")
    khatiyan_number: str = dspy.OutputField(desc="The Khatiyan/Plot (खतियान) number")

class ExplainContent(dspy.Signature):
    """Provide a simple, easy-to-understand explanation of webpage content in plain English.
    Explain what the page is about, its purpose, and key information in 2-3 sentences."""

    content: str = dspy.InputField(desc="The webpage text content")
    title: str = dspy.InputField(desc="The webpage title")
    explanation: str = dspy.OutputField(desc="A simple explanation in plain English")

class AnswerQuestion(dspy.Signature):
    """Answer user questions about webpage content accurately based only on available information."""

    content: str = dspy.InputField(desc="The webpage text content")
    title: str = dspy.InputField(desc="The webpage title")
    question: str = dspy.InputField(desc="The user's question")
    answer: str = dspy.OutputField(desc="The answer based on the webpage content")

class SummarizeContent(dspy.Signature):
    """Provide a clear and concise summary of webpage content with key points."""

    content: str = dspy.InputField(desc="The webpage text content")
    title: str = dspy.InputField(desc="The webpage title")
    summary: str = dspy.OutputField(desc="A concise summary with key points")

# ==================== Agent Classes ====================

class SummarizationAgent:
    """Agent for summarizing webpage content using Claude Sonnet with DSPy"""

    def __init__(self, client: Optional[Anthropic] = None):
        self.client = client
        self.model = "claude-3-5-sonnet-20241022"

        # Initialize DSPy modules
        self.extractor = dspy.ChainOfThought(ExtractKhatiyan)
        self.explainer = dspy.ChainOfThought(ExplainContent)
        self.answerer = dspy.ChainOfThought(AnswerQuestion)
        self.summarizer = dspy.ChainOfThought(SummarizeContent)
    
    async def extract_khatiyan_details(self, content: str, title: str = "") -> dict:
        """Extract Khatiyan details using DSPy"""
        try:
            result = self.extractor(content=content, title=title)
            return {
                "district": result.district or "Not found",
                "tehsil": result.tehsil or "Not found",
                "village": result.village or "Not found",
                "khatiyan_number": result.khatiyan_number or "Not found"
            }
        except Exception as e:
            print(f"Error extracting Khatiyan details with DSPy: {e}")
            return {
                "district": "Extraction failed",
                "tehsil": "Extraction failed",
                "village": "Extraction failed",
                "khatiyan_number": "Extraction failed"
            }

    async def summarize_content(self, content: str, title: str = "") -> str:
        """Summarize webpage content using DSPy"""
        if not self.client:
            return self._fallback_summary(content, title)

        try:
            result = self.summarizer(content=content, title=title)
            return result.summary

        except Exception as e:
            print(f"Error with DSPy summarization: {e}")
            return self._fallback_summary(content, title)
    
    async def answer_question(self, content: str, title: str, question: str) -> str:
        """Answer questions about webpage content using DSPy"""
        if not self.client:
            return self._fallback_answer(content, question)

        try:
            result = self.answerer(content=content, title=title, question=question)
            return result.answer

        except Exception as e:
            print(f"Error with DSPy answering: {e}")
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

    async def explain_content(self, content: str, title: str = "") -> str:
        """Provide a simple, easy-to-understand explanation using DSPy"""
        if not self.client:
            return self._fallback_explanation(content, title)

        try:
            result = self.explainer(content=content, title=title)
            return result.explanation

        except Exception as e:
            print(f"Error with DSPy explanation: {e}")
            return self._fallback_explanation(content, title)

    def _fallback_explanation(self, content: str, title: str) -> str:
        """Fallback explanation when Claude is not available"""
        word_count = len(content.split())
        preview = content[:200] + "..." if len(content) > 200 else content

        return f"""**About this page: {title}**

This page contains {word_count} words. Here's a brief preview:

{preview}

*Note: For a detailed AI-powered explanation, please set the ANTHROPIC_API_KEY environment variable.*"""

# Initialize the summarization agent
summarization_agent = SummarizationAgent(anthropic_client)

# ==================== Supabase Storage Functions ====================

async def get_or_create_khatiyan_record(url: str, title: str, raw_content: str, raw_html: str = None) -> Optional[int]:
    """Get existing or create new khatiyan_record and return its ID"""
    if not supabase_client:
        print("⚠️  Supabase client not available - skipping data storage")
        return None

    try:
        # Try to find existing record by URL (from recent time window to avoid duplicates)
        # Note: In production, you might want more sophisticated deduplication
        result = supabase_client.table("khatiyan_records")\
            .select("id")\
            .eq("url", url)\
            .order("created_at", desc=True)\
            .limit(1)\
            .execute()

        if result.data and len(result.data) > 0:
            record_id = result.data[0]["id"]
            print(f"📌 Found existing khatiyan_record: {record_id}")
            return record_id

        # Create new record
        data = {
            "url": url,
            "title": title,
            "raw_content": raw_content,
            "raw_html": raw_html
        }

        result = supabase_client.table("khatiyan_records").insert(data).execute()
        record_id = result.data[0]["id"]
        print(f"✅ Created new khatiyan_record: {record_id}")
        return record_id

    except Exception as e:
        print(f"❌ Error creating khatiyan_record: {e}")
        return None


async def store_khatiyan_extraction(
    khatiyan_record_id: int,
    extraction_data: dict,
    model_provider: str,
    model_name: str,
    prompt_version: str = "v1",
    extraction_time_ms: int = None,
    tokens_used: int = None
) -> bool:
    """Store AI model extraction to Supabase"""
    if not supabase_client:
        print("⚠️  Supabase client not available - skipping data storage")
        return False

    try:
        data = {
            "khatiyan_record_id": khatiyan_record_id,
            "model_provider": model_provider,
            "model_name": model_name,
            "prompt_version": prompt_version,
            "district": extraction_data.get("district"),
            "tehsil": extraction_data.get("tehsil"),
            "village": extraction_data.get("village"),
            "khatiyan_number": extraction_data.get("khatiyan_number"),
            "extraction_data": extraction_data,  # Full extraction as JSONB
            "extraction_status": "pending",  # Will be updated via user feedback
            "extraction_time_ms": extraction_time_ms,
            "tokens_used": tokens_used
        }

        result = supabase_client.table("khatiyan_extractions").insert(data).execute()
        print(f"✅ Stored extraction from {model_name}: {extraction_data.get('khatiyan_number')}")
        return True

    except Exception as e:
        print(f"❌ Error storing extraction: {e}")
        return False

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

@app.post("/explain")
async def explain_content(webpage: WebpageContent):
    """
    Provide a simple explanation of the webpage content in English and extract Khatiyan details
    """
    import time

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

        # Create or get khatiyan_record
        record_id = await get_or_create_khatiyan_record(
            url=webpage.url,
            title=webpage.title,
            raw_content=text_content,
            raw_html=html_content
        )

        # Extract Khatiyan details using DSPy (with timing)
        extraction_start = time.time()
        khatiyan_data = await summarization_agent.extract_khatiyan_details(text_content, webpage.title)
        extraction_time_ms = int((time.time() - extraction_start) * 1000)

        print(f"Extracted Khatiyan data in {extraction_time_ms}ms: {khatiyan_data}")

        # Store extraction to Supabase (if record was created)
        if record_id:
            await store_khatiyan_extraction(
                khatiyan_record_id=record_id,
                extraction_data=khatiyan_data,
                model_provider="anthropic",
                model_name="claude-3-5-sonnet-20241022",
                prompt_version="v1",  # Increment this when you optimize DSPy prompts
                extraction_time_ms=extraction_time_ms,
                tokens_used=None  # Could be tracked from Anthropic API response if needed
            )

        # Get simple explanation from Claude using DSPy
        explanation = await summarization_agent.explain_content(text_content, webpage.title)

        print(f"Generated explanation for: {webpage.url}")

        return {
            "explanation": explanation,
            "khatiyan_data": khatiyan_data,
            "url": webpage.url,
            "title": webpage.title,
            "record_id": record_id
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating explanation: {str(e)}")

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
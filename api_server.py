from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
import os
from anthropic import Anthropic
from typing import Optional
from dotenv import load_dotenv

# Set DSPy cache directory BEFORE importing dspy (Lambda requires /tmp)
os.environ.setdefault('DSPY_CACHEDIR', '/tmp/.dspy_cache')

import dspy
from supabase import create_client, Client
import asyncio
from prompt_service import PromptService

# Load environment variables from .env file
load_dotenv()

app = FastAPI(title="Webpage Content Chat API")

# Determine environment and configure CORS
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
CHROME_EXTENSION_ID = os.getenv("CHROME_EXTENSION_ID", "")

# Note: API Gateway doesn't support chrome-extension:// origins, so we always use wildcard
# This means we must set allow_credentials=False (CORS spec requirement)
allowed_origins = ["*"]
allow_credentials = False

if ENVIRONMENT == "production" and CHROME_EXTENSION_ID:
    extension_ids = [id.strip() for id in CHROME_EXTENSION_ID.split(",") if id.strip()]
    print(f"🔒 Production mode - CORS allows all origins (API Gateway limitation)")
    print(f"   Security: URL validation restricts to Bhulekha sites only")
    print(f"   Extension IDs tracked: {', '.join(extension_ids)}")
else:
    print("⚠️  Development mode - CORS allows all origins")

# Enable CORS for Chrome extension
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)

# NOTE: page_contexts moved to Supabase for Lambda persistence
# The in-memory dictionary has been replaced with store_page_context() and get_page_context()
# See functions around line 438 for Supabase-backed storage implementation

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

# ==================== Initialize Prompt Service ====================

# Initialize PromptService for dynamic prompt fetching
prompt_service = None
try:
    prompt_service_url = os.getenv("PROMPT_SERVICE_URL", "https://5rp9zvhds7.ap-south-1.awsapprunner.com")
    cache_ttl = int(os.getenv("PROMPT_CACHE_TTL_SECONDS", "3600"))

    prompt_service = PromptService(
        api_base_url=prompt_service_url,
        cache_ttl_seconds=cache_ttl,
        fallback_dir="prompts"
    )
    print(f"✅ Prompt service initialized (url={prompt_service_url}, cache_ttl={cache_ttl}s)")
except Exception as e:
    print(f"⚠️  Could not initialize prompt service: {e}")

# ==================== Load RoR Summary Prompt ====================

# Lazy load RoR summary prompt on first use (to avoid event loop issues in Lambda)
# Note: Deferred loading prevents asyncio.run() at module level which interferes with Mangum
ROR_SUMMARY_PROMPT = None
ROR_SUMMARY_PROMPT_LOADED = False  # Track if we attempted to load

async def load_ror_prompt_if_needed():
    """Lazy load RoR prompt on first use (within async context)

    This avoids using asyncio.run() at module level which creates and closes an event loop,
    interfering with Mangum's event loop management in Lambda.
    """
    global ROR_SUMMARY_PROMPT, ROR_SUMMARY_PROMPT_LOADED

    if ROR_SUMMARY_PROMPT_LOADED:
        return  # Already loaded or attempted

    try:
        if prompt_service:
            ror_prompt_id = int(os.getenv("ROR_SUMMARY_PROMPT_ID", "2"))
            ROR_SUMMARY_PROMPT = await prompt_service.get_prompt(
                prompt_id=ror_prompt_id,
                fallback_filename="ror_summary.txt"
            )
            # Update DSPy signature with fetched prompt
            SummarizeRoR.__doc__ = ROR_SUMMARY_PROMPT
            print(f"✅ Loaded RoR prompt dynamically (id={ror_prompt_id})")
        else:
            # Fallback to local file
            prompt_path = os.path.join(os.path.dirname(__file__), "prompts", "ror_summary.txt")
            with open(prompt_path, 'r', encoding='utf-8') as f:
                ROR_SUMMARY_PROMPT = f.read().strip()
            SummarizeRoR.__doc__ = ROR_SUMMARY_PROMPT
            print("✅ Loaded RoR prompt from local file")
    except Exception as e:
        print(f"⚠️ Could not load RoR prompt: {e}")
        ROR_SUMMARY_PROMPT = "You are a land document expert. Analyze the RoR document and provide a detailed summary."
        SummarizeRoR.__doc__ = ROR_SUMMARY_PROMPT
    finally:
        ROR_SUMMARY_PROMPT_LOADED = True

# ==================== DSPy Signatures ====================

class ExtractKhatiyan(dspy.Signature):
    """Extract ALL structured Khatiyan land record details from Bhulekha webpage content.
    Extract ALL information including district, tehsil, village, khatiyan number, owner details, plots, and any special comments.
    IMPORTANT: Translate all Indic language text to English. All output fields must contain ONLY English text, not Odia or other Indic scripts."""

    content: str = dspy.InputField(desc="The webpage text content")
    title: str = dspy.InputField(desc="The webpage title")

    # Location information (in English)
    district: str = dspy.OutputField(desc="The district (ଜିଲ୍ଲା) name in ENGLISH only")
    tehsil: str = dspy.OutputField(desc="The tehsil/block (ତହସିଲ) name in ENGLISH only")
    village: str = dspy.OutputField(desc="The village (ମୌଜା) name in ENGLISH only")
    khatiyan_number: str = dspy.OutputField(desc="The Khatiyan/Plot (ଖତିୟାନର କ୍ରମିକ ନମ୍ବର) number")

    # Owner information (in English)
    owner_name: str = dspy.OutputField(desc="The primary owner/tenant name (ରୟତ/ଭୂସ୍ୱାମୀ) in ENGLISH only, transliterated from Odia if needed")
    father_name: str = dspy.OutputField(desc="The owner's father name (ପିତାଙ୍କ ନାମ) in ENGLISH only, transliterated from Odia if needed")
    caste: str = dspy.OutputField(desc="The owner's caste/category (ଜାତି) in ENGLISH only, transliterated from Odia if needed")

    # Plot information
    total_plots: str = dspy.OutputField(desc="Total number of plots/land parcels mentioned")
    plot_numbers: str = dspy.OutputField(desc="All plot numbers listed, comma-separated if multiple")
    total_area: str = dspy.OutputField(desc="Total land area with units (acres/decimals/etc)")

    # Additional details (in English)
    land_type: str = dspy.OutputField(desc="Type of land (agricultural/residential/etc) in ENGLISH only")
    special_comments: str = dspy.OutputField(desc="Any special remarks, comments, or notes in ENGLISH only, transliterated from Odia if needed")
    other_owners: str = dspy.OutputField(desc="Names of co-owners or other people mentioned, if any, in ENGLISH only")

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

class SummarizeRoR(dspy.Signature):
    """You are a land document expert for the state of Odisha.
    Provide comprehensive RoR (Record of Rights) analysis with risk assessment, plot details,
    ownership information, and actionable next steps."""

    ror_content: str = dspy.InputField(desc="The complete Record of Rights (RoR) webpage text content")
    title: str = dspy.InputField(desc="The RoR webpage title")

    html_summary: str = dspy.OutputField(
        desc="Complete HTML formatted summary with: 1) Color-coded safety score section at top "
             "(red background for score < 5, yellow for 5-7, light green for > 8), "
             "2) Plot details section with size in acres/sqft, plot numbers, and land use type, "
             "3) Ownership details section with owner name, father's name, caste, and owner type "
             "(Government/Private Citizen/Corporate), "
             "4) Risk/Safety section with bullet points explaining the risk rating, "
             "5) Next steps section with recommendations. "
             "HTML should be well-formatted with proper spacing, bolding, and highlighting of important information."
    )

# Note: RoR prompt docstring is now set dynamically in load_ror_prompt_if_needed()
# when the /summarize endpoint is first called

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
        self.ror_summarizer = dspy.ChainOfThought(SummarizeRoR)
    
    async def extract_khatiyan_details(self, content: str, title: str = "") -> dict:
        """Extract Khatiyan details using DSPy"""
        try:
            result = self.extractor(content=content, title=title)
            return {
                # Location information
                "district": result.district or "Not found",
                "tehsil": result.tehsil or "Not found",
                "village": result.village or "Not found",
                "khatiyan_number": result.khatiyan_number or "Not found",

                # Owner information
                "owner_name": result.owner_name or "Not found",
                "father_name": result.father_name or "Not found",
                "caste": result.caste or "Not found",

                # Plot information
                "total_plots": result.total_plots or "Not found",
                "plot_numbers": result.plot_numbers or "Not found",
                "total_area": result.total_area or "Not found",

                # Additional details
                "land_type": result.land_type or "Not found",
                "special_comments": result.special_comments or "Not found",
                "other_owners": result.other_owners or "Not found"
            }
        except Exception as e:
            print(f"Error extracting Khatiyan details with DSPy: {e}")
            return {
                "district": "Extraction failed",
                "tehsil": "Extraction failed",
                "village": "Extraction failed",
                "khatiyan_number": "Extraction failed",
                "owner_name": "Extraction failed",
                "father_name": "Extraction failed",
                "caste": "Extraction failed",
                "total_plots": "Extraction failed",
                "plot_numbers": "Extraction failed",
                "total_area": "Extraction failed",
                "land_type": "Extraction failed",
                "special_comments": "Extraction failed",
                "other_owners": "Extraction failed"
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

    async def summarize_ror_document(self, content: str, title: str = "") -> str:
        """Generate comprehensive RoR summary with risk assessment and HTML formatting

        Uses the detailed RoR summary prompt from prompts/ror_summary.txt to:
        - Analyze plot details and ownership
        - Calculate safety score (1-10)
        - Identify risks (govt ownership, public land use, corporate ownership)
        - Provide color-coded HTML output
        - Suggest next steps
        """
        if not self.client:
            return self._fallback_ror_summary(content, title)

        try:
            result = self.ror_summarizer(ror_content=content, title=title)
            return result.html_summary

        except Exception as e:
            print(f"Error with DSPy RoR summarization: {e}")
            return self._fallback_ror_summary(content, title)

    def _fallback_ror_summary(self, content: str, title: str) -> str:
        """Fallback RoR summary when Claude is not available"""
        word_count = len(content.split())
        preview = content[:500] + "..." if len(content) > 500 else content

        return f"""<div style="padding: 20px; font-family: Arial, sans-serif;">
    <div style="background-color: #FFC107; padding: 15px; margin-bottom: 20px; border-radius: 5px;">
        <h2 style="margin: 0 0 10px 0;">⚠️ AI Analysis Unavailable</h2>
        <p style="margin: 0;"><strong>Safety Score: Not Available</strong></p>
    </div>

    <h3>Document Preview</h3>
    <p><strong>Title:</strong> {title}</p>
    <p><strong>Content Length:</strong> {word_count} words</p>
    <div style="background-color: #f5f5f5; padding: 15px; border-radius: 5px; margin: 15px 0;">
        <p style="margin: 0;">{preview}</p>
    </div>

    <div style="background-color: #FFF3CD; padding: 15px; margin-top: 20px; border-radius: 5px;">
        <p style="margin: 0;"><strong>Note:</strong> AI-powered RoR analysis requires ANTHROPIC_API_KEY.
        Please configure your API key to get detailed risk assessment, plot analysis, and recommendations.</p>
    </div>
</div>"""

# Initialize the summarization agent
summarization_agent = SummarizationAgent(anthropic_client)

# ==================== Supabase Storage Functions ====================

async def get_or_create_khatiyan_record(
    district: str,
    tehsil: str,
    village: str,
    khatiyan_number: str,
    title: str,
    raw_content: str,
    raw_html: str = None
) -> Optional[int]:
    """Get existing or create new khatiyan_record and return its ID

    Deduplication is based on (district, tehsil, village, khatiyan_number) combination.
    """
    if not supabase_client:
        print("⚠️  Supabase client not available - skipping data storage")
        return None

    try:
        # Try to find existing record by unique key (district, tehsil, village, khatiyan_number)
        result = supabase_client.table("khatiyan_records")\
            .select("id")\
            .eq("district", district)\
            .eq("tehsil", tehsil)\
            .eq("village", village)\
            .eq("khatiyan_number", khatiyan_number)\
            .limit(1)\
            .execute()

        if result.data and len(result.data) > 0:
            record_id = result.data[0]["id"]
            print(f"📌 Found existing khatiyan_record: {record_id} for {district}/{tehsil}/{village}/{khatiyan_number}")
            return record_id

        # Create new record
        data = {
            "district": district,
            "tehsil": tehsil,
            "village": village,
            "khatiyan_number": khatiyan_number,
            "title": title,
            "raw_content": raw_content,
            "raw_html": raw_html
        }

        result = supabase_client.table("khatiyan_records").insert(data).execute()
        record_id = result.data[0]["id"]
        print(f"✅ Created new khatiyan_record: {record_id} for {district}/{tehsil}/{village}/{khatiyan_number}")
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
    """Store AI model extraction to Supabase with JSON-based schema"""
    if not supabase_client:
        print("⚠️  Supabase client not available - skipping data storage")
        return False

    try:
        data = {
            "khatiyan_record_id": khatiyan_record_id,
            "model_provider": model_provider,
            "model_name": model_name,
            "prompt_version": prompt_version,
            "extraction_data": extraction_data,  # All extracted fields stored as JSONB
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

# ==================== Page Context Storage Functions ====================

async def store_page_context(url: str, title: str, text: str, html: str = None) -> bool:
    """Store page context in Supabase for Lambda persistence"""
    if not supabase_client:
        print("⚠️  Supabase client not available - skipping page context storage")
        return False

    try:
        data = {
            "url": url,
            "title": title,
            "text_content": text,
            "html_content": html,
            "word_count": len(text.split()),
            "char_count": len(text),
            "last_accessed": "NOW()"
        }

        # Upsert: update if exists (based on unique url constraint), insert if new
        result = supabase_client.table("page_contexts")\
            .upsert(data, on_conflict="url")\
            .execute()

        print(f"✅ Stored page context for: {url}")
        return True
    except Exception as e:
        print(f"❌ Error storing page context: {e}")
        return False


async def get_page_context(url: str) -> Optional[dict]:
    """Retrieve page context from Supabase"""
    if not supabase_client:
        print("⚠️  Supabase client not available - cannot retrieve page context")
        return None

    try:
        result = supabase_client.table("page_contexts")\
            .select("*")\
            .eq("url", url)\
            .limit(1)\
            .execute()

        if result.data and len(result.data) > 0:
            # Update last_accessed timestamp
            supabase_client.table("page_contexts")\
                .update({"last_accessed": "NOW()"})\
                .eq("url", url)\
                .execute()

            print(f"📖 Retrieved page context for: {url}")
            return result.data[0]

        print(f"⚠️  No page context found for: {url}")
        return None
    except Exception as e:
        print(f"❌ Error retrieving page context: {e}")
        return None

# Define allowed URLs
ALLOWED_URLS = [
    "https://bhulekh.ori.nic.in/SRoRFront_Uni.aspx",
    "https://bhulekh.ori.nic.in/CRoRFront_Uni.aspx"
]

def is_url_allowed(url: str) -> bool:
    """Check if the URL is in the allowed list"""
    return any(url.startswith(allowed_url) for allowed_url in ALLOWED_URLS)

def get_tester_id(request: Request) -> str:
    """Extract tester ID from request headers"""
    return request.headers.get("X-Tester-ID", "anonymous")

class WebpageContent(BaseModel):
    url: str
    title: str
    content: dict  # Contains 'text' and 'html' fields

class ChatQuery(BaseModel):
    query: str
    url: str
    title: str

class FeedbackRequest(BaseModel):
    extraction_id: int
    feedback: str  # 'correct' or 'wrong'
    user_comment: Optional[str] = None

@app.post("/load-content")
async def load_content(webpage: WebpageContent, request: Request):
    """
    Load webpage content and store it for chat context
    """
    try:
        tester_id = get_tester_id(request)
        print(f"📥 [Tester: {tester_id}] /load-content from {webpage.url}")
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

        # Store content in Supabase for Lambda persistence
        success = await store_page_context(
            url=webpage.url,
            title=webpage.title,
            text=text_content,
            html=html_content
        )

        if not success:
            raise HTTPException(
                status_code=500,
                detail="Failed to store page content. Please ensure Supabase is configured."
            )

        print(f"Loaded content from: {webpage.url}")
        print(f"Title: {webpage.title}")
        print(f"Word count: {len(text_content.split())}")

        return {
            "status": "success",
            "message": "Content loaded successfully",
            "word_count": len(text_content.split())
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error loading content: {str(e)}")

@app.post("/chat")
async def chat_with_content(chat: ChatQuery, request: Request):
    """
    Process chat queries about the loaded webpage content
    """
    try:
        tester_id = get_tester_id(request)
        print(f"💬 [Tester: {tester_id}] /chat query: {chat.query[:50]}...")
        # Validate URL - only allow Bhulekh website
        if not is_url_allowed(chat.url):
            allowed_urls_str = ", ".join(ALLOWED_URLS)
            raise HTTPException(
                status_code=403,
                detail=f"Access denied. This service only works with these URLs: {allowed_urls_str}"
            )

        # Get stored content from Supabase
        page_data = await get_page_context(chat.url)

        if not page_data:
            raise HTTPException(
                status_code=404,
                detail="Page content not loaded. Please load the page first."
            )

        text_content = page_data["text_content"]
        page_title = page_data["title"]

        # Use AI-powered responses with Claude Sonnet
        query_lower = chat.query.lower()

        # Check for summary requests
        if "summary" in query_lower or "summarize" in query_lower:
            response = await summarization_agent.summarize_content(text_content, page_title)
        else:
            # Use Claude to answer general questions about the content
            response = await summarization_agent.answer_question(
                text_content,
                page_title,
                chat.query
            )

        print(f"Chat query from {chat.url}: {chat.query}")

        return {
            "response": response,
            "query": chat.query,
            "url": chat.url
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing chat: {str(e)}")

@app.post("/explain")
async def explain_content(webpage: WebpageContent, request: Request):
    """
    Provide a simple explanation of the webpage content in English and extract Khatiyan details
    Uses cached data if available to avoid redundant API calls
    """
    import time

    try:
        tester_id = get_tester_id(request)
        print(f"💡 [Tester: {tester_id}] /explain for {webpage.url}")
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

        # Check for existing cached extraction first
        cached_extraction = None
        cached_explanation = None
        record_id = None

        # First, extract Khatiyan details to get unique identifiers
        extraction_start = time.time()
        khatiyan_data = await summarization_agent.extract_khatiyan_details(text_content, webpage.title)
        extraction_time_ms = int((time.time() - extraction_start) * 1000)
        print(f"🔍 Extracted Khatiyan data in {extraction_time_ms}ms: {khatiyan_data}")

        # Now check if we have this record in database
        if supabase_client and khatiyan_data:
            try:
                district = khatiyan_data.get("district", "")
                tehsil = khatiyan_data.get("tehsil", "")
                village = khatiyan_data.get("village", "")
                khatiyan_number = khatiyan_data.get("khatiyan_number", "")

                if district and tehsil and village and khatiyan_number:
                    # Look for existing record by unique key
                    record_result = supabase_client.table("khatiyan_records")\
                        .select("id")\
                        .eq("district", district)\
                        .eq("tehsil", tehsil)\
                        .eq("village", village)\
                        .eq("khatiyan_number", khatiyan_number)\
                        .limit(1)\
                        .execute()

                    if record_result.data and len(record_result.data) > 0:
                        record_id = record_result.data[0]["id"]
                        print(f"📌 Found existing record {record_id} for {district}/{tehsil}/{village}/{khatiyan_number}")

                        # Check for recent extraction (within 24 hours) to avoid re-extraction
                        extraction_result = supabase_client.table("khatiyan_extractions")\
                            .select("extraction_data, created_at")\
                            .eq("khatiyan_record_id", record_id)\
                            .eq("model_name", "claude-3-5-sonnet-20241022")\
                            .eq("prompt_version", "v1")\
                            .gte("created_at", "now() - interval '24 hours'")\
                            .order("created_at", desc=True)\
                            .limit(1)\
                            .execute()

                        if extraction_result.data and len(extraction_result.data) > 0:
                            cached_extraction = extraction_result.data[0]["extraction_data"]
                            print(f"✅ Using cached extraction from database (created: {extraction_result.data[0]['created_at']})")
                            khatiyan_data = cached_extraction
                            extraction_time_ms = 0  # Cache hit - overwrite with 0
            except Exception as e:
                print(f"⚠️  Error checking cache: {e}")

        # Create/get record if we don't have it yet and have valid data
        if not record_id and khatiyan_data and supabase_client:
            district = khatiyan_data.get("district", "")
            tehsil = khatiyan_data.get("tehsil", "")
            village = khatiyan_data.get("village", "")
            khatiyan_number = khatiyan_data.get("khatiyan_number", "")

            if district and tehsil and village and khatiyan_number:
                record_id = await get_or_create_khatiyan_record(
                    district=district,
                    tehsil=tehsil,
                    village=village,
                    khatiyan_number=khatiyan_number,
                    title=webpage.title,
                    raw_content=text_content,
                    raw_html=html_content
                )

        # Store extraction to Supabase (if not cached and record exists)
        if record_id and not cached_extraction:
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
            "record_id": record_id,
            "cached": cached_extraction is not None
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

@app.post("/get-extraction")
async def get_extraction(webpage: WebpageContent, request: Request):
    """
    Get the latest extraction data for the given page by first extracting its identifiers
    and looking up by (district, tehsil, village, khatiyan_number)
    """
    try:
        tester_id = get_tester_id(request)
        print(f"📊 [Tester: {tester_id}] /get-extraction for {webpage.url}")
        # Validate URL - only allow Bhulekh website
        if not is_url_allowed(webpage.url):
            allowed_urls_str = ", ".join(ALLOWED_URLS)
            raise HTTPException(
                status_code=403,
                detail=f"Access denied. This service only works with these URLs: {allowed_urls_str}"
            )

        if not supabase_client:
            raise HTTPException(
                status_code=503,
                detail="Database not available. Please configure Supabase connection."
            )

        # Extract content to identify the khatiyan
        text_content = webpage.content.get('text', '')

        # Extract khatiyan identifiers from the current page
        khatiyan_data = await summarization_agent.extract_khatiyan_details(text_content, webpage.title)

        district = khatiyan_data.get("district", "")
        tehsil = khatiyan_data.get("tehsil", "")
        village = khatiyan_data.get("village", "")
        khatiyan_number = khatiyan_data.get("khatiyan_number", "")

        if not district or not tehsil or not village or not khatiyan_number:
            raise HTTPException(
                status_code=404,
                detail="Could not extract location identifiers from the page. Please ensure this is a valid Khatiyan page."
            )

        # Find the khatiyan_record by unique identifiers
        record_result = supabase_client.table("khatiyan_records")\
            .select("id")\
            .eq("district", district)\
            .eq("tehsil", tehsil)\
            .eq("village", village)\
            .eq("khatiyan_number", khatiyan_number)\
            .limit(1)\
            .execute()

        if not record_result.data or len(record_result.data) == 0:
            raise HTTPException(
                status_code=404,
                detail="No extraction found for this page. Please load the page content first using 'Help me understand' button."
            )

        record_id = record_result.data[0]["id"]

        # Get the latest extraction for this record
        extraction_result = supabase_client.table("khatiyan_extractions")\
            .select("*")\
            .eq("khatiyan_record_id", record_id)\
            .order("created_at", desc=True)\
            .limit(1)\
            .execute()

        if not extraction_result.data or len(extraction_result.data) == 0:
            raise HTTPException(
                status_code=404,
                detail="No extraction data found for this page."
            )

        extraction = extraction_result.data[0]
        extraction_data = extraction.get("extraction_data", {})

        # Format the extraction data for display
        formatted_data = {
            "location": {
                "district": extraction_data.get("district"),
                "tehsil": extraction_data.get("tehsil"),
                "village": extraction_data.get("village"),
                "khatiyan_number": extraction_data.get("khatiyan_number")
            },
            "owner_details": {
                "owner_name": extraction_data.get("owner_name"),
                "father_name": extraction_data.get("father_name"),
                "caste": extraction_data.get("caste"),
                "other_owners": extraction_data.get("other_owners")
            },
            "plot_information": {
                "total_plots": extraction_data.get("total_plots"),
                "plot_numbers": extraction_data.get("plot_numbers"),
                "total_area": extraction_data.get("total_area"),
                "land_type": extraction_data.get("land_type")
            },
            "additional_info": {
                "special_comments": extraction_data.get("special_comments")
            },
            "metadata": {
                "model_name": extraction.get("model_name"),
                "extraction_time_ms": extraction.get("extraction_time_ms"),
                "created_at": extraction.get("created_at")
            }
        }

        return {
            "status": "success",
            "data": formatted_data,
            "url": webpage.url,
            "extraction_id": extraction.get("id")  # Include extraction_id for feedback
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving extraction: {str(e)}")

@app.post("/submit-feedback")
async def submit_feedback(feedback: FeedbackRequest, request: Request):
    """
    Submit user feedback on extraction quality (thumbs up/down)
    Stores feedback in user_feedback column with timestamp
    """
    try:
        tester_id = get_tester_id(request)
        print(f"👍👎 [Tester: {tester_id}] /submit-feedback: {feedback.feedback} for extraction {feedback.extraction_id}")
        if not supabase_client:
            raise HTTPException(
                status_code=503,
                detail="Database not available. Please configure Supabase connection."
            )

        # Validate feedback value
        if feedback.feedback not in ['correct', 'wrong']:
            raise HTTPException(
                status_code=400,
                detail="Feedback must be 'correct' or 'wrong'"
            )

        # Update the extraction record - store in user_feedback, not extraction_status
        update_data = {
            "user_feedback": feedback.feedback,
            "feedback_timestamp": "NOW()"
        }

        # Add optional user comment if provided
        if feedback.user_comment:
            update_data["user_feedback"] = f"{feedback.feedback}: {feedback.user_comment}"

        result = supabase_client.table("khatiyan_extractions")\
            .update(update_data)\
            .eq("id", feedback.extraction_id)\
            .execute()

        if not result.data:
            raise HTTPException(
                status_code=404,
                detail="Extraction not found"
            )

        return {
            "status": "success",
            "message": f"Feedback recorded as '{feedback.feedback}'"
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error submitting feedback: {str(e)}")

@app.post("/summarize")
async def summarize_page(webpage: WebpageContent, request: Request):
    """
    Generate comprehensive RoR summary with risk assessment

    Returns HTML-formatted summary with:
    - Safety score (1-10) with color-coded background
    - Plot details (size, type, numbers)
    - Ownership analysis (govt/corporate/citizen classification)
    - Risk assessment with reasoning
    - Recommended next steps
    """
    import time

    try:
        # Lazy load prompt on first use (avoids event loop issues in Lambda)
        await load_ror_prompt_if_needed()

        tester_id = get_tester_id(request)
        print(f"📝 [Tester: {tester_id}] /summarize for {webpage.url}")
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

        # Generate RoR summary using DSPy
        summary_start = time.time()
        html_summary = await summarization_agent.summarize_ror_document(
            text_content,
            webpage.title
        )
        summary_time_ms = int((time.time() - summary_start) * 1000)

        print(f"📝 Generated RoR summary in {summary_time_ms}ms for: {webpage.url}")

        # Optional: Store summary in database for caching
        # (Can implement later with a ror_summaries table)

        return {
            "status": "success",
            "url": webpage.url,
            "title": webpage.title,
            "html_summary": html_summary,
            "generation_time_ms": summary_time_ms
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error generating RoR summary: {e}")
        raise HTTPException(status_code=500, detail=f"Error generating summary: {str(e)}")

# ==================== Lambda Handler ====================

# Import Mangum for AWS Lambda compatibility
try:
    from mangum import Mangum
    # Create Lambda handler with lifespan="off" to avoid startup/shutdown issues
    handler = Mangum(app, lifespan="off")
    print("✅ Lambda handler configured with Mangum")
except ImportError:
    print("⚠️  Mangum not installed - Lambda deployment not available")
    handler = None

# For local development, keep the uvicorn runner
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
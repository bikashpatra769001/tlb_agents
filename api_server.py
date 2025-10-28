from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
import os
import logging
from anthropic import Anthropic
from typing import Optional
from dotenv import load_dotenv
from datetime import datetime, timedelta, timezone

# Set DSPy cache directory BEFORE importing dspy (Lambda requires /tmp)
os.environ.setdefault('DSPY_CACHEDIR', '/tmp/.dspy_cache')

import dspy
from supabase import create_client, Client
import asyncio
from prompt_service import PromptService
from html_parser import BhulekhaHTMLParser

# Load environment variables from .env file
load_dotenv()

# Load secrets from AWS Parameter Store (with .env fallback for local dev)
from aws_secrets import get_secrets
secrets = get_secrets()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Webpage Content Chat API")

# Determine environment and configure CORS
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
CHROME_EXTENSION_ID = secrets.get("chrome_extension_id", "")

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
    api_key = secrets.get("anthropic_api_key")
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
    supabase_url = secrets.get("supabase_url")
    supabase_key = secrets.get("supabase_key")
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
    prompt_service_url = secrets.get("prompt_service_url", "https://5rp9zvhds7.ap-south-1.awsapprunner.com")
    cache_ttl = int(os.getenv("PROMPT_CACHE_TTL_SECONDS", "3600"))
    max_retries = int(os.getenv("PROMPT_MAX_RETRIES", "3"))
    timeout = float(os.getenv("PROMPT_TIMEOUT_SECONDS", "30.0"))

    prompt_service = PromptService(
        api_base_url=prompt_service_url,
        cache_ttl_seconds=cache_ttl,
        fallback_dir="prompts",
        max_retries=max_retries,
        timeout=timeout
    )
    print(f"✅ Prompt service initialized (url={prompt_service_url}, cache_ttl={cache_ttl}s, max_retries={max_retries}, timeout={timeout}s)")
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

    After loading the prompt, recreates the RoR summarizer module so DSPy compiles with the new docstring.
    """
    global ROR_SUMMARY_PROMPT, ROR_SUMMARY_PROMPT_LOADED

    if ROR_SUMMARY_PROMPT_LOADED:
        return  # Already loaded or attempted

    try:
        if prompt_service:
            ror_prompt_id = int(os.getenv("ROR_SUMMARY_PROMPT_ID", "2"))
            logger.info(f"Loading RoR summary prompt from service (id={ror_prompt_id})")
            ROR_SUMMARY_PROMPT = await prompt_service.get_prompt(
                prompt_id=ror_prompt_id,
                fallback_filename="ror_summary.txt"
            )
            # Update DSPy signature with fetched prompt
            SummarizeRoR.__doc__ = ROR_SUMMARY_PROMPT
            # Note: The prompt_service already logs the actual source (API/cache/file)
            logger.info(f"✅ RoR prompt loaded successfully via prompt service (length={len(ROR_SUMMARY_PROMPT)} chars)")
        else:
            # Fallback to local file when prompt_service is unavailable
            logger.warning("⚠️ PromptService not available, loading RoR prompt from local fallback file")
            prompt_path = os.path.join(os.path.dirname(__file__), "prompts", "ror_summary.txt")
            with open(prompt_path, 'r', encoding='utf-8') as f:
                ROR_SUMMARY_PROMPT = f.read().strip()
            SummarizeRoR.__doc__ = ROR_SUMMARY_PROMPT
            logger.info(f"✅ Loaded RoR prompt from local file: {prompt_path} (length={len(ROR_SUMMARY_PROMPT)} chars)")
            print(f"✅ Loaded RoR prompt from local fallback file (PromptService unavailable)")
    except Exception as e:
        logger.error(f"❌ Failed to load RoR prompt from all sources: {e}", exc_info=True)
        print(f"⚠️ Could not load RoR prompt: {e}")
        ROR_SUMMARY_PROMPT = "You are a land document expert. Analyze the RoR document and provide a detailed summary."
        SummarizeRoR.__doc__ = ROR_SUMMARY_PROMPT
        logger.warning("Using hardcoded fallback RoR prompt")
    finally:
        ROR_SUMMARY_PROMPT_LOADED = True

        # IMPORTANT: Recreate the RoR summarizer so DSPy compiles with the new docstring
        # This ensures the loaded prompt (not the placeholder) is used
        summarization_agent.ror_summarizer = dspy.ChainOfThought(SummarizeRoR)
        logger.info("🔄 Recreated RoR summarizer with updated prompt")

# ==================== DSPy Signatures ====================

class ExtractKhatiyan(dspy.Signature):
    """Extract ALL structured Khatiyan land record details from Bhulekha webpage content.

    CRITICAL EXTRACTION REQUIREMENTS:
    1. For location names (district, tehsil, village): Extract BOTH formats when available:
       - English transliteration (e.g., "Khordha", "Bhubaneswar", "Patia")
       - Native Odia script (e.g., "ଖୋର୍ଦ୍ଧା", "ଭୁବନେଶ୍ୱର", "ପାଟିଆ")

    2. Search the content carefully for text in Odia script (looks like: ଜିଲ୍ଲା, ତହସିଲ, ମୌଜା, etc.)

    3. If native Odia text is present, extract it EXACTLY as shown. If not present, leave the native fields empty.

    4. For other fields (owner names, etc.), translate Indic language text to English.

    Extract ALL information including district, tehsil, village, khatiyan number, owner details, plots, and any special comments."""

    content: str = dspy.InputField(desc="The webpage text content containing both Odia script and English text")
    title: str = dspy.InputField(desc="The webpage title")

    # Location information (English transliteration)
    district: str = dspy.OutputField(desc="District name in ENGLISH (e.g., 'Khordha', 'Cuttack'). Look for ଜିଲ୍ଲା label.")
    tehsil: str = dspy.OutputField(desc="Tehsil/Tahasil/Block name in ENGLISH (e.g., 'Bhubaneswar'). Look for ତହସିଲ label.")
    village: str = dspy.OutputField(desc="Village/Mouza name in ENGLISH (e.g., 'Patia'). Look for ମୌଜା label.")
    khatiyan_number: str = dspy.OutputField(desc="Khatiyan number (e.g., '1234'). Look for ଖତିୟାନର କ୍ରମିକ ନମ୍ବର label.")

    # Location information (Native Odia script) - Extract EXACTLY as shown
    native_district: str = dspy.OutputField(desc="District name in ODIA SCRIPT ONLY (e.g., 'ଖୋର୍ଦ୍ଧା'). Copy the Odia text that appears after ଜିଲ୍ଲା label. Leave empty if no Odia script found.")
    native_tehsil: str = dspy.OutputField(desc="Tehsil name in ODIA SCRIPT ONLY (e.g., 'ଭୁବନେଶ୍ୱର'). Copy the Odia text that appears after ତହସିଲ label. Leave empty if no Odia script found.")
    native_village: str = dspy.OutputField(desc="Village name in ODIA SCRIPT ONLY (e.g., 'ପାଟିଆ'). Copy the Odia text that appears after ମୌଜା label. Leave empty if no Odia script found.")

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

class TranslateOdiaToEnglish(dspy.Signature):
    """Translate a structured Khatiyan land record JSON from Odia (both keys and values) to English (both keys and values).

    CRITICAL TRANSLATION REQUIREMENTS:
    1. Translate ALL Odia keys to their English equivalents (e.g., ଜିଲ୍ଲା → district, ମାଲିକ_ନାମ → owner_name)
    2. Translate ALL Odia values to English:
       - Place names: Use official English names when available (e.g., କଟକ → Cuttack, ଖୋର୍ଦ୍ଧା → Khordha)
       - Person names: Use proper English transliteration (e.g., ସୁରେଶ କୁମାର → Suresh Kumar)
       - Caste names: Transliterate properly (e.g., ଖଣ୍ଡାୟତ → Khandayat)
       - Land types: Translate descriptive terms (e.g., ଘରବାଡି → Gharabari/Residential)
    3. Preserve the exact same JSON structure as input
    4. Keep numeric values EXACTLY as-is (plot numbers, areas, dates, etc.)
    5. Return valid JSON format with English keys following this mapping:
       - ଜିଲ୍ଲା → district
       - ତହସିଲ → tehsil
       - ଗ୍ରାମ → village
       - ଖତିୟାନ_ନମ୍ବର → khatiyan_number
       - ମାଲିକ_ନାମ → owner_name
       - ପିତା_ନାମ → father_name
       - ଜାତି → caste
       - ମୋଟ_ପ୍ଲଟ → total_plots
       - ପ୍ଲଟ_ନମ୍ବର → plot_numbers
       - ମୋଟ_କ୍ଷେତ୍ରଫଳ → total_area
       - ଜମି_ପ୍ରକାର → land_type
       - ଅନ୍ୟ_ମାଲିକ → other_owners
       - ବିଶେଷ_ମନ୍ତବ୍ୟ → special_comments
    """

    odia_json: str = dspy.InputField(desc="JSON string with Odia keys and Odia values extracted from Bhulekha RoR document")
    english_json: str = dspy.OutputField(desc="JSON string with English keys and English translated values, maintaining the same structure")

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
    
    async def extract_khatiyan_details(self, content: str, title: str = "") -> tuple[dict, dict]:
        """Extract Khatiyan details using DSPy

        Returns:
            tuple: (extraction_data, prompt_config)
        """
        try:
            result = self.extractor(content=content, title=title)

            # Capture the DSPy prompt immediately after the call
            prompt_config = get_last_dspy_prompt(
                signature_name="ExtractKhatiyan",
                module_type="ChainOfThought"
            )

            # Extract native language fields (may be None or empty)
            native_district = getattr(result, 'native_district', None) or None
            native_tehsil = getattr(result, 'native_tehsil', None) or None
            native_village = getattr(result, 'native_village', None) or None

            # Debug logging to see what Claude extracted
            print(f"🔍 Extracted native fields:")
            print(f"   native_district: {native_district}")
            print(f"   native_tehsil: {native_tehsil}")
            print(f"   native_village: {native_village}")

            extraction_data = {
                # Location information (English)
                "district": result.district or "Not found",
                "tehsil": result.tehsil or "Not found",
                "village": result.village or "Not found",
                "khatiyan_number": result.khatiyan_number or "Not found",

                # Location information (Native Odia script)
                "native_district": native_district,
                "native_tehsil": native_tehsil,
                "native_village": native_village,

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

            return extraction_data, prompt_config

        except Exception as e:
            print(f"Error extracting Khatiyan details with DSPy: {e}")
            extraction_data = {
                "district": "Extraction failed",
                "tehsil": "Extraction failed",
                "village": "Extraction failed",
                "khatiyan_number": "Extraction failed",
                "native_district": None,
                "native_tehsil": None,
                "native_village": None,
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
            return extraction_data, None

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

    async def translate_odia_to_english(self, odia_data: dict) -> dict:
        """Translate Odia JSON (Odia keys + Odia values) to English JSON (English keys + English values)

        Args:
            odia_data: Dictionary with Odia keys and Odia values from HTML parser

        Returns:
            Dictionary with English keys and English translated values

        Raises:
            Exception: If translation fails or produces invalid JSON
        """
        if not self.client:
            raise Exception("ANTHROPIC_API_KEY not set - translation requires Claude API access")

        import json

        try:
            # Initialize translator
            translator = dspy.ChainOfThought(TranslateOdiaToEnglish)

            # Convert dict to JSON string for LLM
            odia_json_str = json.dumps(odia_data, ensure_ascii=False, indent=2)

            print(f"🔄 Translating Odia JSON to English via LLM...")
            print(f"   Input: {odia_json_str[:100]}...")

            # Call LLM for translation
            result = translator(odia_json=odia_json_str)

            # Parse the English JSON response
            english_data = json.loads(result.english_json)

            print(f"✅ Translation complete: {len(english_data)} fields translated")

            return english_data

        except json.JSONDecodeError as e:
            print(f"❌ Error: LLM returned invalid JSON: {e}")
            print(f"   Raw response: {result.english_json}")
            raise Exception(f"Translation failed - invalid JSON from LLM: {e}")

        except Exception as e:
            print(f"❌ Error translating Odia to English: {e}")
            raise

    async def summarize_ror_document(self, content: str, title: str = "") -> tuple[str, dict]:
        """Generate comprehensive RoR summary with risk assessment and HTML formatting

        Uses the detailed RoR summary prompt from prompts/ror_summary.txt to:
        - Analyze plot details and ownership
        - Calculate safety score (1-10)
        - Identify risks (govt ownership, public land use, corporate ownership)
        - Provide color-coded HTML output
        - Suggest next steps

        Returns:
            tuple: (html_summary, prompt_config)
        """
        if not self.client:
            return self._fallback_ror_summary(content, title), None

        try:
            result = self.ror_summarizer(ror_content=content, title=title)

            # Capture the DSPy prompt immediately after the call
            prompt_config = get_last_dspy_prompt(
                signature_name="SummarizeRoR",
                module_type="ChainOfThought"
            )

            return result.html_summary, prompt_config

        except Exception as e:
            print(f"Error with DSPy RoR summarization: {e}")
            return self._fallback_ror_summary(content, title), None

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

# ==================== DSPy Prompt Extraction ====================

def get_last_dspy_prompt(signature_name: str = None, module_type: str = "ChainOfThought") -> Optional[dict]:
    """Extract the last prompt sent to LLM from DSPy's LM history

    Returns a dict containing:
    - model: The model name used
    - signature: The DSPy signature name
    - dspy_module: The module type (ChainOfThought, Predict, etc)
    - messages: The actual messages sent to the LLM
    - temperature: Temperature setting (if available)
    - max_tokens: Max tokens setting (if available)
    """
    try:
        lm = dspy.settings.lm
        if not lm or not hasattr(lm, 'history') or not lm.history:
            logger.warning("No DSPy LM history available")
            return None

        # Get the last call from history
        last_call = lm.history[-1]

        # Extract prompt information
        prompt_config = {
            "model": getattr(lm, 'model', 'unknown'),
            "signature": signature_name,
            "dspy_module": module_type,
            "messages": last_call.get('messages', []),
            "temperature": getattr(lm, 'temperature', None) if hasattr(lm, 'temperature') else None,
            "max_tokens": getattr(lm, 'max_tokens', None) if hasattr(lm, 'max_tokens') else None,
        }

        logger.info(f"Captured DSPy prompt for {signature_name} ({len(prompt_config['messages'])} messages)")
        return prompt_config

    except Exception as e:
        logger.error(f"Error extracting DSPy prompt: {e}", exc_info=True)
        return None

# ==================== Supabase Storage Functions ====================

async def get_or_create_khatiyan_record(
    district: str,
    tehsil: str,
    village: str,
    khatiyan_number: str,
    title: str,
    raw_content: str,
    raw_html: str = None,
    native_district: str = None,
    native_tehsil: str = None,
    native_village: str = None
) -> Optional[int]:
    """Get existing or create new khatiyan_record and return its ID

    Deduplication is based on (district, tehsil, village, khatiyan_number) combination.
    Native language names are stored but not used for deduplication.
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
            "raw_html": raw_html,
            "native_district": native_district,
            "native_tehsil": native_tehsil,
            "native_village": native_village
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
    extraction_data_en: dict,
    extraction_data_od: dict,
    model_provider: str,
    model_name: str,
    prompt_version: str = "v1",
    extraction_time_ms: int = None,
    prompt_config: dict = None,
    extraction_method: str = None,
    parser_confidence: str = None
) -> bool:
    """Store AI model or HTML parser extraction to Supabase with dual-language JSON schema"""
    if not supabase_client:
        print("⚠️  Supabase client not available - skipping data storage")
        return False

    try:
        data = {
            "khatiyan_record_id": khatiyan_record_id,
            "model_provider": model_provider,
            "model_name": model_name,
            "prompt_version": prompt_version,
            "extraction_data_en": extraction_data_en,  # English JSON (English keys + values)
            "extraction_data_od": extraction_data_od,  # Odia JSON (Odia keys + values)
            "extraction_status": "pending",  # Will be updated via user feedback
            "extraction_time_ms": extraction_time_ms,
            "prompt_config": prompt_config,  # Store DSPy prompt and config
            "extraction_method": extraction_method,  # "html_parser" only (no LLM fallback)
            "parser_confidence": parser_confidence  # "high", "medium", "low"
        }

        result = supabase_client.table("khatiyan_extractions").insert(data).execute()
        print(f"✅ Stored dual-language extraction from {model_name}: {extraction_data_en.get('khatiyan_number')}")
        return True

    except Exception as e:
        print(f"❌ Error storing extraction: {e}")
        return False

async def store_khatiyan_summary(
    khatiyan_record_id: int,
    html_summary: str,
    model_provider: str,
    model_name: str,
    prompt_version: str = "v1",
    generation_time_ms: int = None,
    prompt_config: dict = None
) -> Optional[int]:
    """Store AI-generated summary to khatiyan_summaries table"""
    if not supabase_client:
        print("⚠️  Supabase client not available - skipping summary storage")
        return None

    try:
        data = {
            "khatiyan_record_id": khatiyan_record_id,
            "model_provider": model_provider,
            "model_name": model_name,
            "prompt_version": prompt_version,
            "summary_html": html_summary,
            "generation_time_ms": generation_time_ms,
            "summarization_status": "pending",  # Will be updated via user feedback
            "prompt_config": prompt_config  # Store DSPy prompt and config
        }

        result = supabase_client.table("khatiyan_summaries").insert(data).execute()
        summary_id = result.data[0]["id"]
        print(f"✅ Stored summary {summary_id} for record {khatiyan_record_id}")
        return summary_id

    except Exception as e:
        print(f"❌ Error storing summary: {e}")
        return None

async def get_cached_summary(
    khatiyan_record_id: int,
    model_name: str,
    prompt_version: str = "v1"
) -> Optional[dict]:
    """Get cached summary from khatiyan_summaries table if exists and recent (<24h)"""
    if not supabase_client:
        print("⚠️  Supabase client not available - cannot retrieve cached summary")
        return None

    try:
        # Calculate 24 hours ago timestamp
        twenty_four_hours_ago = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()

        result = supabase_client.table("khatiyan_summaries")\
            .select("id, summary_html, generation_time_ms, created_at")\
            .eq("khatiyan_record_id", khatiyan_record_id)\
            .eq("model_name", model_name)\
            .eq("prompt_version", prompt_version)\
            .gte("created_at", twenty_four_hours_ago)\
            .order("created_at", desc=True)\
            .limit(1)\
            .execute()

        if result.data and len(result.data) > 0:
            cached = result.data[0]
            print(f"✅ Found cached summary (summary_id: {cached['id']})")
            return cached

        return None

    except Exception as e:
        print(f"❌ Error retrieving cached summary: {e}")
        return None

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
            "last_accessed": datetime.now(timezone.utc).isoformat()
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
                .update({"last_accessed": datetime.now(timezone.utc).isoformat()})\
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

        # Step 1: Extract Odia JSON from HTML using parser
        extraction_start = time.time()
        parser = BhulekhaHTMLParser(html_content)
        khatiyan_data_od, confidence = parser.extract_khatiyan_details()
        extraction_time_ms = int((time.time() - extraction_start) * 1000)

        extraction_method = "html_parser"
        parser_confidence = confidence
        prompt_config = None

        print(f"🔍 HTML parser extracted Odia data in {extraction_time_ms}ms with {confidence} confidence")

        # If parser confidence is not high, return error to user
        if confidence != "high":
            logger.warning(f"Parser confidence {confidence}, returning error to user")
            print(f"❌ Parser confidence {confidence}, extraction failed")

            raise HTTPException(
                status_code=422,
                detail=f"Unable to extract data from this page. Parser confidence: {confidence}. Please verify the page format or try a different RoR page."
            )

        print(f"✅ Extracted Odia JSON: {khatiyan_data_od}")

        # Step 2: Translate Odia JSON to English JSON using LLM
        translation_start = time.time()
        try:
            khatiyan_data_en = await summarization_agent.translate_odia_to_english(khatiyan_data_od)
            translation_time_ms = int((time.time() - translation_start) * 1000)
            print(f"✅ Translated to English in {translation_time_ms}ms: {khatiyan_data_en}")
        except Exception as e:
            logger.error(f"Translation failed: {e}")
            print(f"❌ Translation failed: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Extraction successful but translation failed: {str(e)}"
            )

        # Now check if we have this record in database
        if supabase_client and khatiyan_data_en:
            try:
                district = khatiyan_data_en.get("district", "")
                tehsil = khatiyan_data_en.get("tehsil", "")
                village = khatiyan_data_en.get("village", "")
                khatiyan_number = khatiyan_data_en.get("khatiyan_number", "")

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
                        twenty_four_hours_ago = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()

                        extraction_result = supabase_client.table("khatiyan_extractions")\
                            .select("extraction_data_en, extraction_data_od, created_at")\
                            .eq("khatiyan_record_id", record_id)\
                            .eq("model_name", "beautifulsoup4")\
                            .eq("prompt_version", "v1")\
                            .gte("created_at", twenty_four_hours_ago)\
                            .order("created_at", desc=True)\
                            .limit(1)\
                            .execute()

                        if extraction_result.data and len(extraction_result.data) > 0:
                            cached_extraction = extraction_result.data[0]
                            print(f"✅ Using cached extraction from database (created: {extraction_result.data[0]['created_at']})")
                            khatiyan_data_en = cached_extraction["extraction_data_en"]
                            khatiyan_data_od = cached_extraction["extraction_data_od"]
                            extraction_time_ms = 0  # Cache hit - overwrite with 0
            except Exception as e:
                print(f"⚠️  Error checking cache: {e}")

        # Create/get record if we don't have it yet and have valid data
        if not record_id and khatiyan_data_en and supabase_client:
            district = khatiyan_data_en.get("district", "")
            tehsil = khatiyan_data_en.get("tehsil", "")
            village = khatiyan_data_en.get("village", "")
            khatiyan_number = khatiyan_data_en.get("khatiyan_number", "")

            # Get native names from Odia JSON
            native_district = khatiyan_data_od.get("ଜିଲ୍ଲା")
            native_tehsil = khatiyan_data_od.get("ତହସିଲ")
            native_village = khatiyan_data_od.get("ଗ୍ରାମ")

            if district and tehsil and village and khatiyan_number:
                record_id = await get_or_create_khatiyan_record(
                    district=district,
                    tehsil=tehsil,
                    village=village,
                    khatiyan_number=khatiyan_number,
                    title=webpage.title,
                    raw_content=text_content,
                    raw_html=html_content,
                    native_district=native_district,
                    native_tehsil=native_tehsil,
                    native_village=native_village
                )

        # Store extraction to Supabase (if not cached and record exists)
        if record_id and not cached_extraction:
            # Always use HTML parser (no LLM fallback)
            model_provider = "html_parser"
            model_name = "beautifulsoup4"

            await store_khatiyan_extraction(
                khatiyan_record_id=record_id,
                extraction_data_en=khatiyan_data_en,
                extraction_data_od=khatiyan_data_od,
                model_provider=model_provider,
                model_name=model_name,
                prompt_version="v1",
                extraction_time_ms=extraction_time_ms,
                prompt_config=prompt_config,  # None for HTML parser
                extraction_method=extraction_method,
                parser_confidence=parser_confidence
            )

        # Get simple explanation from Claude using DSPy
        explanation = await summarization_agent.explain_content(text_content, webpage.title)

        print(f"Generated explanation for: {webpage.url}")

        return {
            "explanation": explanation,
            "khatiyan_data": khatiyan_data_en,  # Return English data for backward compatibility
            "khatiyan_data_en": khatiyan_data_en,  # Explicit English data
            "khatiyan_data_od": khatiyan_data_od,  # Explicit Odia data
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
        khatiyan_data, _ = await summarization_agent.extract_khatiyan_details(text_content, webpage.title)

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
    Stores feedback status in extraction_status column, optional comments in extraction_user_feedback
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

        # Update the extraction record - store feedback status in extraction_status
        update_data = {
            "extraction_status": feedback.feedback,  # 'correct' or 'wrong'
            "feedback_timestamp": datetime.now(timezone.utc).isoformat()
        }

        # Store optional user comment in extraction_user_feedback column
        if feedback.user_comment:
            update_data["extraction_user_feedback"] = feedback.user_comment

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

@app.post("/submit-summary-feedback")
async def submit_summary_feedback(feedback: FeedbackRequest, request: Request):
    """
    Submit user feedback on summary quality (thumbs up/down)
    Stores feedback in khatiyan_summaries table

    Note: Uses extraction_id field from FeedbackRequest model but it refers to summary_id
    """
    try:
        tester_id = get_tester_id(request)
        summary_id = feedback.extraction_id  # Reuse extraction_id field for summary_id
        print(f"👍👎 [Tester: {tester_id}] /submit-summary-feedback: {feedback.feedback} for summary {summary_id}")
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

        # Update the summary record - store feedback status in summarization_status
        update_data = {
            "summarization_status": feedback.feedback,  # 'correct' or 'wrong'
            "feedback_timestamp": datetime.now(timezone.utc).isoformat()
        }

        # Store optional user comment in summarization_user_feedback column
        if feedback.user_comment:
            update_data["summarization_user_feedback"] = feedback.user_comment

        result = supabase_client.table("khatiyan_summaries")\
            .update(update_data)\
            .eq("id", summary_id)\
            .execute()

        if not result.data:
            raise HTTPException(
                status_code=404,
                detail="Summary not found"
            )

        return {
            "status": "success",
            "message": f"Summary feedback recorded as '{feedback.feedback}'"
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error submitting summary feedback: {str(e)}")

@app.post("/summarize")
async def summarize_page(webpage: WebpageContent, request: Request):
    """
    Generate comprehensive RoR summary with risk assessment (with caching)

    Returns HTML-formatted summary with:
    - Safety score (1-10) with color-coded background
    - Plot details (size, type, numbers)
    - Ownership analysis (govt/corporate/citizen classification)
    - Risk assessment with reasoning
    - Recommended next steps

    Caching: Summaries are cached for 24 hours per unique khatiyan record
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

        # Extract khatiyan details to get identifiers for caching
        extraction_start = time.time()
        khatiyan_data, _ = await summarization_agent.extract_khatiyan_details(
            text_content, webpage.title
        )

        district = khatiyan_data.get("district", "")
        tehsil = khatiyan_data.get("tehsil", "")
        village = khatiyan_data.get("village", "")
        khatiyan_number = khatiyan_data.get("khatiyan_number", "")

        record_id = None
        cached_summary = None

        # Get or create khatiyan_record for caching
        if district and tehsil and village and khatiyan_number:
            record_id = await get_or_create_khatiyan_record(
                district=district,
                tehsil=tehsil,
                village=village,
                khatiyan_number=khatiyan_number,
                title=webpage.title,
                raw_content=text_content,
                raw_html=html_content,
                native_district=khatiyan_data.get("native_district"),
                native_tehsil=khatiyan_data.get("native_tehsil"),
                native_village=khatiyan_data.get("native_village")
            )

            # Check for cached summary
            if record_id:
                cached_summary = await get_cached_summary(
                    khatiyan_record_id=record_id,
                    model_name="claude-3-5-sonnet-20241022",
                    prompt_version="v1"
                )

        # Return cached summary if available
        if cached_summary:
            print(f"📦 Returning cached summary (summary_id: {cached_summary['id']})")
            return {
                "status": "success",
                "url": webpage.url,
                "title": webpage.title,
                "html_summary": cached_summary["summary_html"],
                "generation_time_ms": cached_summary.get("generation_time_ms", 0),
                "summary_id": cached_summary["id"],
                "cached": True
            }

        # Generate new summary using DSPy
        summary_start = time.time()
        html_summary, prompt_config = await summarization_agent.summarize_ror_document(
            text_content,
            webpage.title
        )
        summary_time_ms = int((time.time() - summary_start) * 1000)

        # Store summary in database
        summary_id = None
        if record_id:
            summary_id = await store_khatiyan_summary(
                khatiyan_record_id=record_id,
                html_summary=html_summary,
                model_provider="anthropic",
                model_name="claude-3-5-sonnet-20241022",
                prompt_version="v1",
                generation_time_ms=summary_time_ms,
                prompt_config=prompt_config  # Store the actual DSPy prompt
            )

        print(f"📝 Generated new summary in {summary_time_ms}ms for: {webpage.url}")

        return {
            "status": "success",
            "url": webpage.url,
            "title": webpage.title,
            "html_summary": html_summary,
            "generation_time_ms": summary_time_ms,
            "summary_id": summary_id,
            "cached": False
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
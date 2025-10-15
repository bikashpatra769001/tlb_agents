# Bhulekha Extension - Distribution Package

## Package Contents

This beta testing package contains:

1. **bhulekha-extension-v1.0.zip** - The Chrome extension
2. **BETA_TESTING_GUIDE.md** - Complete instructions for beta testers
3. **DISTRIBUTION_README.md** - This file

---

## For Beta Testers

### Quick Start

1. Download `bhulekha-extension-v1.0.zip`
2. Open Chrome → `chrome://extensions/`
3. Enable "Developer mode"
4. Drag and drop the .zip file onto the page
5. Enter your tester ID when prompted
6. Navigate to https://bhulekh.ori.nic.in/SRoRFront_Uni.aspx
7. The sidebar will automatically open with page analysis!

**Full instructions**: See `BETA_TESTING_GUIDE.md`

---

## Extension Features

### 1. Collapsible Sidebar Interface

The extension now opens as a **sidebar** that slides in from the right side of the page, keeping the original webpage content visible.

**Toggle Sidebar:**
- **Keyboard Shortcut**: `Ctrl+Shift+B` (Windows/Linux) or `Cmd+Shift+B` (Mac)
- **Floating Button**: Click the 🌾 button in the bottom-right corner
- **Smooth Animation**: Sidebar slides in/out with a 300ms animation

**Why Sidebar?**
- Doesn't cover the webpage content like a popup would
- Easy to show/hide while reviewing land records
- Convenient keyboard shortcut for quick access

### 2. Automatic Page Analysis

When you navigate to a Bhulekh page, the extension automatically:
1. **Reads** the page content
2. **Extracts** land record details (district, tehsil, village, khatiyan number, owner info)
3. **Explains** the page in simple English
4. **Stores** data in the database for caching

### 3. Action Buttons

Four powerful buttons at the bottom of the sidebar:

#### 📊 Show Details
- Displays extracted land record information in a structured format
- Shows: Location, Owner Details, Plot Information, Special Comments
- Includes **feedback buttons** (👍 Correct / 👎 Wrong)
- Data is cached - second click loads instantly from database

#### 📝 Summarize
- Generates a comprehensive RoR (Record of Rights) summary
- Includes:
  - **Safety Score** (1-10) with color-coded risk indicator
  - **Plot Details** (size, plot numbers, land use type)
  - **Ownership Analysis** (government/private/corporate classification)
  - **Risk Assessment** with explanations
  - **Next Steps** and recommendations
- **Cached for 24 hours** - shows cache indicator if loaded from database
- Includes **feedback buttons** (👍 Helpful / 👎 Not Helpful)

#### 📋 Apply EC (Encumbrance Certificate)
- Provides step-by-step instructions for applying for EC
- AI-powered guidance based on the current page

#### 📄 Apply CC (Conversion Certificate)
- Provides step-by-step instructions for applying for CC
- AI-powered guidance based on the current page

### 4. Feedback System

**Two Types of Feedback:**

1. **Extraction Feedback** (from "Show Details")
   - 👍 Correct - Data extracted accurately
   - 👎 Wrong - Data has errors

2. **Summary Feedback** (from "Summarize")
   - 👍 Helpful - Summary was useful and accurate
   - 👎 Not Helpful - Summary was missing info or inaccurate

**Feedback Flow:**
- Click 👍 (Thumbs Up) → Instantly submits positive feedback
- Click 👎 (Thumbs Down) → Opens a modal asking "What went wrong?"
  - You can describe the issue (optional)
  - Or skip and submit feedback without comment
- All feedback is stored in Supabase with your tester ID

**Why Feedback Matters:**
- Helps improve AI accuracy over time
- Identifies common extraction errors
- Tracks model performance per field (district, owner name, etc.)
- Can be used to optimize prompts with DSPy

### 5. Tester ID System

**First-Time Setup:**
- On first use, a modal prompts you to enter a Tester ID
- Examples: `Tester_Alice`, `John_Doe`, `Beta_User_1`
- ID is stored in Chrome Sync (persists across devices)

**Why Tester IDs?**
- Track usage patterns per tester
- Identify which testers provide the most feedback
- Analyze bugs reported by specific testers
- Monitor API usage per tester

**Changing Your ID:**
- Currently requires clearing extension storage
- Future update: Settings UI to change ID

---

## How to Use (Step-by-Step)

### First Time Setup

1. **Install Extension**
   - Go to `chrome://extensions/`
   - Enable "Developer mode" (toggle in top-right)
   - Drag `bhulekha-extension-v1.0.zip` onto the page
   - Extension installs with ID: `hknfgjmgpcdehabepbgifofnglkiihgb`

2. **Set Your Tester ID**
   - A modal appears asking for your tester ID
   - Enter a unique name (e.g., `Tester_YourName`)
   - Click "Save & Continue"
   - ID is saved and won't be asked again

### Using the Extension

1. **Open a Bhulekh Page**
   - Navigate to: https://bhulekh.ori.nic.in/SRoRFront_Uni.aspx
   - Or: https://bhulekh.ori.nic.in/CRoRFront_Uni.aspx
   - The sidebar automatically opens on the right side

2. **Review the Explanation**
   - The sidebar shows an AI-generated explanation of the page
   - Read it to understand what the page contains

3. **Try Action Buttons**

   **Get Structured Data:**
   - Click **📊 Show Details**
   - Review extracted information (location, owner, plots)
   - Provide feedback: 👍 if correct, 👎 if wrong
   - If wrong, describe the error (e.g., "Owner name should be 'Ram Kumar' not 'Rama Kumar'")

   **Get Summary:**
   - Click **📝 Summarize**
   - Review the comprehensive RoR summary with safety score
   - Check if it's marked as "Cached" (loaded from database)
   - Provide feedback: 👍 if helpful, 👎 if not helpful

   **Get Instructions:**
   - Click **📋 Apply EC** or **📄 Apply CC**
   - Follow the AI-generated step-by-step instructions

4. **Toggle Sidebar**
   - Press `Ctrl+Shift+B` to hide sidebar (view full page)
   - Press `Ctrl+Shift+B` again to show sidebar
   - Or click the 🌾 button in bottom-right corner

### What to Test

**Extraction Accuracy:**
- [ ] District name correctly extracted?
- [ ] Tehsil name correctly extracted?
- [ ] Village name correctly extracted?
- [ ] Khatiyan number correctly extracted?
- [ ] Owner name correctly extracted (Odia → English transliteration)?
- [ ] Father's name correctly extracted?
- [ ] Plot numbers correctly extracted?
- [ ] Total area correctly extracted?

**Summary Quality:**
- [ ] Is the safety score reasonable?
- [ ] Are plot details accurate?
- [ ] Is ownership analysis correct (government/private)?
- [ ] Are risks identified correctly?
- [ ] Are next steps actionable?

**User Experience:**
- [ ] Does the sidebar animation work smoothly?
- [ ] Does the keyboard shortcut work?
- [ ] Does the floating toggle button work?
- [ ] Are loading spinners shown during AI processing?
- [ ] Do feedback buttons work correctly?

**Caching:**
- [ ] Second click on "Show Details" loads instantly (cached)?
- [ ] Second click on "Summarize" shows cache indicator?
- [ ] Cache expires after 24 hours?

---

## For Administrators

### Extension Details

- **Name**: Bhulekha Content Reader
- **Version**: 1.0
- **Extension ID**: `hknfgjmgpcdehabepbgifofnglkiihgb`
- **Type**: Manifest V3 Chrome Extension
- **Architecture**: Sidebar-based interface with content script injection

### Technical Stack

**Frontend (Chrome Extension)**:
- TypeScript → JavaScript (compiled with tsc)
- Chrome Extensions Manifest V3
- Chrome Storage API for tester ID persistence
- Chrome Commands API for keyboard shortcuts
- Chrome Scripting API for content injection
- Fetch API for backend communication
- IFrame-based sidebar for style isolation

**Backend (AWS Lambda)**:
- FastAPI + Mangum adapter
- Claude 3.5 Sonnet (`claude-3-5-sonnet-20241022`)
- DSPy for programmable prompting
- Supabase (PostgreSQL) for:
  - Page content caching
  - Extraction data storage
  - Summary caching (24-hour TTL)
  - Feedback tracking
- Docker container deployment (2048MB memory, 300s timeout)

**Infrastructure**:
- AWS Lambda (ap-south-1 - Mumbai region)
- Amazon ECR (Container Registry)
- API Gateway HTTP API
- CloudWatch Logs
- Function URL: `https://wyt8w11xp0.execute-api.ap-south-1.amazonaws.com`

### API Endpoints

| Endpoint | Method | Purpose | Caching |
|----------|--------|---------|---------|
| `/health` | GET | Health check | No |
| `/load-content` | POST | Store page content | Yes (Supabase) |
| `/explain` | POST | Generate explanation + extract data | Yes (24h) |
| `/get-extraction` | POST | Retrieve extracted data | Yes |
| `/summarize` | POST | Generate RoR summary | Yes (24h) |
| `/chat` | POST | Answer questions about page | No |
| `/submit-feedback` | POST | Submit extraction feedback | No |
| `/submit-summary-feedback` | POST | Submit summary feedback | No |

### Database Schema

**khatiyan_records** (stores unique land records):
- Deduplication by (district, tehsil, village, khatiyan_number)
- One record per unique khatiyan
- Stores raw content and HTML

**khatiyan_extractions** (stores AI outputs):
- Links to khatiyan_record
- Stores extraction_data (JSONB)
- Stores summary_html
- Tracks model, prompt version, performance
- Stores feedback (extraction_status, summarization_status)
- Stores user comments (extraction_user_feedback, summarization_user_feedback)

**page_contexts** (stores page content for Lambda):
- Stores page text/HTML for chat context
- Upsert by URL (prevents duplicates)
- Tracks last_accessed timestamp

### Tester Tracking

**How It Works**:
- Each tester sets an identifier on first use (e.g., `Tester_Alice`)
- ID is stored in Chrome Sync Storage (persistent across devices)
- All API requests include `X-Tester-ID` header
- Backend logs tester ID for every endpoint call
- Supabase tracks which tester submitted feedback

**View Logs**:
```bash
aws logs tail /aws/lambda/bhulekha-extension --region ap-south-1 --follow
```

Example log entries:
```
📥 [Tester: Tester_Alice] /load-content from https://bhulekh.ori.nic.in/...
💡 [Tester: Tester_Alice] /explain for https://bhulekh.ori.nic.in/...
📝 [Tester: Tester_Bob] /summarize for https://bhulekh.ori.nic.in/...
👍👎 [Tester: Tester_Charlie] /submit-feedback: correct for extraction 42
```

### CORS Security

**Production Mode** (currently active):
- API Gateway allows all origins (chrome-extension:// not supported)
- Security enforced by:
  - URL validation (only Bhulekh URLs allowed)
  - Extension ID tracking (logged in CloudWatch)
  - CORS credentials disabled (spec requirement for wildcard)

**Extension ID Tracking**:
- Environment variable: `CHROME_EXTENSION_ID=hknfgjmgpcdehabepbgifofnglkiihgb`
- Logged in CloudWatch for monitoring
- All beta testers share the same extension ID (same packaged .zip)

### Distributing to New Testers

**Option 1: Same Package (Recommended)**
- Share `bhulekha-extension-v1.0.zip` with new testers
- All testers use the same extension ID
- No configuration needed
- Track testers by their self-chosen tester ID

**Option 2: Create New Package**
- Rebuild and repackage → New extension ID
- Update Lambda environment variable
- Redistribute to all testers

---

## Deployment Information

### Current Deployment

- **Status**: ✅ Production ready
- **Region**: ap-south-1 (Mumbai)
- **API Endpoint**: https://wyt8w11xp0.execute-api.ap-south-1.amazonaws.com
- **Extension ID**: hknfgjmgpcdehabepbgifofnglkiihgb
- **Lambda Function**: bhulekha-extension
- **Container Image**: 293232900878.dkr.ecr.ap-south-1.amazonaws.com/bhulekha-extension-api:latest
- **Last Updated**: 2025-10-15

### Cost Estimate (Monthly)

**Base Cost** (minimal usage):
- **Lambda**: ~$3.60 (1000 requests, 8s avg execution)
- **API Gateway**: ~$0.01 (1000 requests)
- **ECR Storage**: ~$0.10 (container image storage)
- **Total**: ~$3.71/month

**Beta Testing** (5 testers, 50 requests each = 250 requests):
- **Lambda**: ~$18/month (increased execution time for AI processing)
- **API Gateway**: ~$0.03
- **ECR**: ~$0.10
- **Total**: ~$18.13/month

**Note**: Claude API costs are separate (billed by Anthropic)

### Updating the Extension

If you make changes to the extension code:

```bash
# 1. Navigate to extension directory
cd chrome-extension

# 2. Update code in src/ (TypeScript files)
# Example: src/popup.ts, src/sidebar.ts, src/content.ts

# 3. Rebuild TypeScript
npm run build

# 4. Test locally
# Load unpacked extension from chrome-extension/ folder

# 5. Repackage for distribution
cd ..
zip -r bhulekha-extension-v1.1.zip chrome-extension/ \
  -x "chrome-extension/*.git*" \
  -x "chrome-extension/node_modules/*" \
  -x "chrome-extension/.DS_Store" \
  -x "chrome-extension/src/*" \
  -x "chrome-extension/tsconfig.json" \
  -x "chrome-extension/package*.json"

# 6. Distribute new package to testers
# ⚠️ Note: Extension ID will change if you repackage!
```

### Updating the Backend

If you make changes to api_server.py:

```bash
# Quick method: Use deployment script
./deploy-container.sh

# Manual method:
# 1. Update code in api_server.py or prompts/

# 2. Rebuild Docker image
docker build --platform linux/amd64 -t bhulekha-extension-api:latest .

# 3. Push to ECR
aws ecr get-login-password --region ap-south-1 | \
  docker login --username AWS --password-stdin \
  293232900878.dkr.ecr.ap-south-1.amazonaws.com

docker tag bhulekha-extension-api:latest \
  293232900878.dkr.ecr.ap-south-1.amazonaws.com/bhulekha-extension-api:latest

docker push 293232900878.dkr.ecr.ap-south-1.amazonaws.com/bhulekha-extension-api:latest

# 4. Update Lambda
aws lambda update-function-code \
  --function-name bhulekha-extension \
  --image-uri 293232900878.dkr.ecr.ap-south-1.amazonaws.com/bhulekha-extension-api:latest \
  --region ap-south-1

# 5. Wait for update
aws lambda wait function-updated \
  --function-name bhulekha-extension \
  --region ap-south-1
```

---

## Monitoring

### View Real-Time Logs

```bash
# View logs with tester tracking
aws logs tail /aws/lambda/bhulekha-extension --region ap-south-1 --follow

# Filter by specific tester
aws logs tail /aws/lambda/bhulekha-extension --region ap-south-1 --follow | grep "Tester_Alice"

# View errors only
aws logs tail /aws/lambda/bhulekha-extension --region ap-south-1 --follow | grep "ERROR\|❌"
```

### Check Lambda Status

```bash
aws lambda get-function --function-name bhulekha-extension --region ap-south-1
```

### Test Health Endpoint

```bash
curl https://wyt8w11xp0.execute-api.ap-south-1.amazonaws.com/health
# Expected: {"status":"healthy"}
```

### Monitor Supabase

```sql
-- View recent feedback
SELECT
  ke.id,
  kr.district,
  kr.village,
  kr.khatiyan_number,
  ke.extraction_status,
  ke.extraction_user_feedback,
  ke.created_at
FROM khatiyan_extractions ke
JOIN khatiyan_records kr ON ke.khatiyan_record_id = kr.id
WHERE ke.extraction_status IN ('correct', 'wrong')
ORDER BY ke.created_at DESC
LIMIT 20;

-- View summary feedback
SELECT
  ke.id,
  kr.district,
  kr.village,
  ke.summarization_status,
  ke.summarization_user_feedback,
  ke.created_at
FROM khatiyan_extractions ke
JOIN khatiyan_records kr ON ke.khatiyan_record_id = kr.id
WHERE ke.summarization_status IN ('correct', 'wrong')
ORDER BY ke.created_at DESC
LIMIT 20;

-- Accuracy stats
SELECT
  extraction_status,
  COUNT(*) as count
FROM khatiyan_extractions
WHERE extraction_status != 'pending'
GROUP BY extraction_status;
```

---

## Troubleshooting

### Extension Not Loading
- Ensure Developer Mode is enabled in `chrome://extensions/`
- Check that .zip file is not corrupted
- Try reloading the extension
- Check Chrome console for errors (F12 → Console)

### Sidebar Not Appearing
- Ensure you're on a supported URL (SRoRFront_Uni.aspx or CRoRFront_Uni.aspx)
- Try the keyboard shortcut: `Ctrl+Shift+B`
- Click the 🌾 floating button in bottom-right
- Check content script loaded (F12 → Console should show "Bhulekha Extension: Content script loaded")

### Keyboard Shortcut Not Working
- Check for conflicts: `chrome://extensions/shortcuts`
- Try changing the shortcut if needed
- Ensure page has focus (click on page first)
- Background service worker should show: "Bhulekha Extension: Background service worker loaded"

### API Not Responding
- Check Lambda function status (may be in cold start - first request takes 5-10 seconds)
- View CloudWatch logs for errors
- Test health endpoint: `curl https://wyt8w11xp0.execute-api.ap-south-1.amazonaws.com/health`
- Verify Lambda is in "Active" state (not updating)

### Loading Spinner Stuck
- Lambda may be in cold start (wait 10-15 seconds)
- Check internet connection
- View CloudWatch logs for backend errors
- Try reloading the page

### Feedback Not Submitting
- Check network tab (F12 → Network) for failed requests
- Verify tester ID is set (should not be "anonymous")
- Check extraction_id exists (needed for feedback)
- View CloudWatch logs for backend errors

### Tester ID Not Saving
- Check extension has "storage" permission in manifest.json
- Clear extension data: `chrome://extensions/` → Details → "Remove extension"
- Reinstall and try again
- Ensure Chrome Sync is enabled (Settings → Sync)

### Cache Not Working
- Check Supabase connection (backend should log "✅ Supabase client initialized")
- Verify database tables exist (khatiyan_records, khatiyan_extractions)
- Check timestamp functions (should use Python datetime, not SQL NOW())
- View CloudWatch for PostgreSQL errors

### PostgreSQL Timestamp Errors
If you see errors like `invalid input syntax for type timestamp with time zone: "NOW()"`:
- Ensure api_server.py uses Python datetime objects
- Should use: `datetime.now(timezone.utc).isoformat()`
- NOT: `"NOW()"` or `"now() - interval '24 hours'"`
- Redeploy backend after fixing

---

## Support Contacts

- **Technical Issues**: [Your Email]
- **AWS/Lambda Issues**: [Your Email]
- **Extension Distribution**: [Your Email]
- **Feedback/Bug Reports**: [Your Email]

---

## File Structure

```
bhulekha_extension/tlb_agents/
├── bhulekha-extension-v1.0.zip     # Packaged extension
├── BETA_TESTING_GUIDE.md            # For beta testers
├── DISTRIBUTION_README.md           # This file
├── DEPLOYMENT.md                    # Deployment guide
├── CLAUDE.md                        # Project overview
├── api_server.py                    # Backend code (FastAPI)
├── Dockerfile                       # Container definition
├── deploy-container.sh              # Automated deployment script
├── sync-secrets-to-aws.sh           # Sync .env to Parameter Store
├── .env.prod                        # Production secrets (not in git)
├── chrome-extension/                # Extension source
│   ├── src/                         # TypeScript source files
│   │   ├── popup.ts                 # Popup interface (legacy)
│   │   ├── sidebar.ts               # Sidebar interface (main UI)
│   │   ├── content.ts               # Content script (sidebar injection)
│   │   └── background.ts            # Background service worker (keyboard shortcuts)
│   ├── dist/                        # Compiled JavaScript
│   │   ├── popup.js
│   │   ├── sidebar.js
│   │   ├── content.js
│   │   └── background.js
│   ├── manifest.json                # Extension manifest
│   ├── popup.html                   # Popup HTML (legacy)
│   ├── popup.css                    # Popup styles
│   ├── sidebar.html                 # Sidebar HTML (main UI)
│   ├── sidebar.css                  # Sidebar styles
│   ├── icon16.png                   # Extension icons
│   ├── icon48.png
│   ├── icon128.png
│   ├── tsconfig.json                # TypeScript config
│   └── package.json                 # NPM dependencies
├── prompts/                         # Prompt templates
│   └── ror_summary.txt              # RoR summary prompt
└── schema.sql                       # Supabase database schema
```

---

## Changelog

### Version 1.0 (2025-10-15)

**Features:**
- ✅ Collapsible sidebar interface
- ✅ Keyboard shortcut (Ctrl+Shift+B)
- ✅ Floating toggle button
- ✅ Automatic page analysis on load
- ✅ Show Details button with extraction feedback
- ✅ Summarize button with RoR analysis and feedback
- ✅ Apply EC/CC buttons
- ✅ Tester ID system
- ✅ Feedback modals with optional comments
- ✅ Loading spinners for AI processing
- ✅ 24-hour caching for summaries and extractions
- ✅ PostgreSQL timestamp fixes for proper caching

**Backend:**
- ✅ FastAPI on AWS Lambda (ap-south-1)
- ✅ Claude 3.5 Sonnet integration
- ✅ DSPy for programmable prompting
- ✅ Supabase for data storage
- ✅ Docker container deployment
- ✅ Tester tracking with X-Tester-ID header
- ✅ CloudWatch logging

**Infrastructure:**
- ✅ API Gateway HTTP API
- ✅ Amazon ECR for container storage
- ✅ AWS Parameter Store for secrets
- ✅ CORS configuration for security

---

**Generated**: 2025-10-15
**Version**: 1.0
**Region**: ap-south-1 (Mumbai)

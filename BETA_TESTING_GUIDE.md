# Bhulekha Extension - Beta Testing Guide

## Overview

Thank you for participating in the Bhulekha Chrome Extension beta test! This extension helps you understand and extract information from Bhulekh land records using AI-powered analysis.

**Key Features:**
- 🌾 **Collapsible Sidebar** - Doesn't block the webpage content
- ⌨️ **Keyboard Shortcut** - Quick toggle with `Ctrl+Shift+B`
- 🤖 **Automatic Analysis** - Page analyzed as soon as you open it
- 📊 **Structured Extraction** - District, tehsil, village, owner details, plot info
- 📝 **RoR Summary** - Comprehensive summary with safety score
- 👍👎 **Feedback System** - Help improve the AI with your feedback

---

## Installation Instructions

### Step 1: Download the Extension

You should have received:
- `bhulekha-extension-v1.0.zip` - The extension package

### Step 2: Install in Chrome

1. Open Google Chrome
2. Navigate to `chrome://extensions/`
3. Enable **"Developer mode"** (toggle in top right corner)
4. Drag and drop the `bhulekha-extension-v1.0.zip` file onto the extensions page
5. The extension should install automatically
6. You'll see "Bhulekha Content Reader" installed with a 🌾 icon

### Step 3: First-Time Setup

1. Navigate to a Bhulekh page (see URLs below)
2. The sidebar will automatically open on the right side
3. A **Tester ID modal** will appear
4. Enter your tester ID (examples: `Tester_Alice`, `John_Doe`, `Beta_User_1`)
5. Click **"Save & Continue"**
6. Your ID is saved in Chrome Sync and you won't be asked again

**Note**: Your tester ID helps us track usage patterns and feedback. Only use letters, numbers, underscores, and hyphens.

---

## How to Use the Extension

### 1. Navigate to Bhulekh Website

The extension only works on:
- `https://bhulekh.ori.nic.in/SRoRFront_Uni.aspx` (Survey RoR)
- `https://bhulekh.ori.nic.in/CRoRFront_Uni.aspx` (Cadastral RoR)

### 2. Automatic Sidebar Opens

When you open a Bhulekh page:
1. The sidebar **automatically slides in** from the right side
2. You'll see a loading spinner with "Reading page content..."
3. The AI analyzes the page (takes 5-10 seconds)
4. An **explanation** of the page appears in simple English
5. Four **action buttons** appear at the bottom

**Toggling the Sidebar:**
- **Keyboard**: Press `Ctrl+Shift+B` (Windows/Linux) or `Cmd+Shift+B` (Mac)
- **Floating Button**: Click the 🌾 button in the bottom-right corner
- The sidebar slides in/out smoothly

### 3. Features to Test

#### 📊 Show Details Button

Displays extracted land record information in a structured format.

**What it shows:**
- **Location Information**
  - District (e.g., "Khordha")
  - Tehsil (e.g., "Bhubaneswar")
  - Village (e.g., "Patia")
  - Khatiyan Number (e.g., "123/456")

- **Owner Details**
  - Owner Name (translated from Odia to English)
  - Father's Name
  - Caste (if available)
  - Other Owners (if multiple owners)

- **Plot Information**
  - Total Plots
  - Plot Numbers (comma-separated)
  - Total Area (with units)
  - Land Type (agricultural/residential/etc.)

- **Special Comments** (if any)

**How to use:**
1. Click **📊 Show Details**
2. Review the extracted data
3. Provide feedback:
   - Click **👍 Correct** if all data is accurate
   - Click **👎 Wrong** if any data is incorrect
4. If you clicked **👎 Wrong**, a modal appears:
   - Describe what's wrong (e.g., "Owner name should be 'Ram Kumar' not 'Rama Kumar'")
   - Or click **Skip** to submit without comment

**Caching:** Second click loads instantly from database (no AI processing needed).

#### 📝 Summarize Button

Generates a comprehensive RoR (Record of Rights) summary with risk assessment.

**What it includes:**
- **Safety Score** (1-10) with color-coded indicator
  - Red background: Score < 5 (high risk)
  - Yellow background: Score 5-7 (medium risk)
  - Green background: Score > 8 (low risk)

- **Plot Details**
  - Land size in acres/square feet
  - Plot numbers
  - Land use type (agricultural/residential/commercial)

- **Ownership Analysis**
  - Owner type classification:
    - Government ownership
    - Private citizen
    - Corporate ownership
  - Owner name and details

- **Risk Assessment**
  - Bullet points explaining the safety score
  - Identified risks (e.g., government land, disputed ownership, etc.)

- **Next Steps**
  - Actionable recommendations
  - Suggested verifications
  - Legal considerations

**How to use:**
1. Click **📝 Summarize**
2. Wait for AI to generate summary (10-15 seconds)
3. Review the comprehensive analysis
4. Check if it shows **📦 Cached summary** (loaded from database)
5. Provide feedback:
   - Click **👍 Helpful** if summary is accurate and useful
   - Click **👎 Not Helpful** if summary is missing info or inaccurate
6. If you clicked **👎 Not Helpful**, a modal appears:
   - Describe what was missing or wrong
   - Or click **Skip** to submit without comment

**Caching:** Summaries are cached for 24 hours. Second click within 24 hours loads instantly with a cache indicator.

#### 📋 Apply EC (Encumbrance Certificate)

Provides step-by-step instructions for applying for an Encumbrance Certificate.

**How to use:**
1. Click **📋 Apply EC**
2. Wait for AI response (5-10 seconds)
3. Read the step-by-step instructions
4. Follow the guidance based on the current page

#### 📄 Apply CC (Conversion Certificate)

Provides step-by-step instructions for applying for a Conversion Certificate.

**How to use:**
1. Click **📄 Apply CC**
2. Wait for AI response (5-10 seconds)
3. Read the step-by-step instructions
4. Follow the guidance based on the current page

### 4. Understanding the Feedback System

**Two Types of Feedback:**

1. **Extraction Feedback** (from "Show Details"):
   - 👍 Correct = All extracted data is accurate
   - 👎 Wrong = Some data is incorrect

2. **Summary Feedback** (from "Summarize"):
   - 👍 Helpful = Summary is useful and accurate
   - 👎 Not Helpful = Summary is missing info or inaccurate

**Feedback Flow:**
- **Thumbs Up** → Immediately submits positive feedback
- **Thumbs Down** → Opens a modal asking for details:
  - **Text area** to describe the issue (optional)
  - **Submit Feedback** button
  - **Skip** button (submits feedback without comment)

**Why Your Feedback Matters:**
- Helps identify common extraction errors
- Improves AI accuracy over time
- Tracks which fields are most error-prone
- Can be used to optimize AI prompts with DSPy

**Examples of Good Feedback:**
- ❌ "Wrong" (too vague)
- ✅ "Owner name should be 'Ramesh Kumar' not 'Ramesa Kumar'"
- ✅ "District is correct but village name is wrong - should be 'Patia' not 'Patiya'"
- ✅ "Summary safety score seems too high - land is actually government owned"
- ✅ "Missing information about plot boundaries in summary"

---

## What to Test

Please test ALL features and report any issues:

### 1. Installation & Setup
- [ ] Extension installs successfully from .zip file
- [ ] Tester ID modal appears on first use
- [ ] Tester ID saves correctly (doesn't ask again on reload)
- [ ] Chrome Sync keeps your ID across devices (if enabled)

### 2. Sidebar Functionality
- [ ] Sidebar automatically opens when visiting Bhulekh page
- [ ] Sidebar slides in smoothly from right side
- [ ] Keyboard shortcut (`Ctrl+Shift+B`) toggles sidebar
- [ ] Floating 🌾 button works in bottom-right corner
- [ ] Sidebar doesn't block webpage content
- [ ] Can view both sidebar and webpage simultaneously

### 3. Automatic Analysis
- [ ] Page content loads automatically (no button click needed)
- [ ] Loading spinner appears during AI processing
- [ ] Explanation appears in simple English
- [ ] Explanation accurately describes the page

### 4. Show Details Feature
- [ ] **📊 Show Details** button works
- [ ] Loading spinner appears during extraction
- [ ] Extracted data appears in structured format
- [ ] All sections present (Location, Owner, Plot, Comments)
- [ ] Data accuracy:
  - [ ] District name correct
  - [ ] Tehsil name correct
  - [ ] Village name correct
  - [ ] Khatiyan number correct
  - [ ] Owner name correct (Odia → English transliteration)
  - [ ] Father's name correct
  - [ ] Plot numbers correct
  - [ ] Total area correct with units
  - [ ] Land type makes sense
- [ ] Feedback buttons appear (👍 Correct / 👎 Wrong)
- [ ] Clicking 👍 immediately submits feedback
- [ ] Clicking 👎 opens modal asking for details
- [ ] Modal allows submitting with or without comment
- [ ] Second click loads data instantly (cached)

### 5. Summarize Feature
- [ ] **📝 Summarize** button works
- [ ] Loading spinner appears during generation
- [ ] Summary appears with HTML formatting
- [ ] Safety score is present and color-coded
- [ ] Plot details section is present and accurate
- [ ] Ownership analysis is present and reasonable
- [ ] Risk assessment is present with explanations
- [ ] Next steps are actionable
- [ ] Feedback buttons appear (👍 Helpful / 👎 Not Helpful)
- [ ] Clicking 👍 immediately submits feedback
- [ ] Clicking 👎 opens modal asking for details
- [ ] Second click within 24 hours shows "📦 Cached summary"
- [ ] Cached summary loads instantly

### 6. Apply EC/CC Features
- [ ] **📋 Apply EC** button works
- [ ] AI provides step-by-step instructions
- [ ] Instructions are relevant to the page
- [ ] **📄 Apply CC** button works
- [ ] AI provides step-by-step instructions

### 7. User Experience
- [ ] Interface is intuitive and easy to use
- [ ] Loading spinners clearly indicate AI is processing
- [ ] Loading messages are informative (e.g., "Generating summary...")
- [ ] Error messages are clear if something goes wrong
- [ ] Buttons are clearly labeled and understandable
- [ ] Text is readable (good contrast, font size)
- [ ] No UI elements overlap or look broken

### 8. Performance
- [ ] First request (cold start): 15-30 seconds
- [ ] Subsequent requests: 5-10 seconds
- [ ] Cached requests: < 1 second (instant)
- [ ] Page doesn't freeze during AI processing
- [ ] Can toggle sidebar while AI is processing

### 9. Edge Cases
- [ ] Works with very long Khatiyan documents
- [ ] Works with multiple owners listed
- [ ] Works with special characters in names
- [ ] Works with different districts/tehsils/villages
- [ ] Handles pages with missing information gracefully
- [ ] Works on both SRoRFront_Uni.aspx and CRoRFront_Uni.aspx

---

## Known Limitations

- **First request takes longer** (cold start): 15-30 seconds (Lambda warming up)
- **Subsequent requests are faster**: 5-10 seconds
- **Cached data loads instantly**: < 1 second
- **Only works on Bhulekh website**: Won't activate on other sites
- **Requires internet connection**: Uses cloud AI services (AWS Lambda + Claude AI)
- **Cache expires after 24 hours**: After 24h, fresh AI processing is required
- **Odia to English transliteration**: May not be perfect for all names

---

## Reporting Issues

### When You Find a Bug

Please provide:
1. **Your Tester ID** (e.g., `Tester_Alice`)
2. **Which feature** (Sidebar toggle, Show Details, Summarize, Apply EC/CC)
3. **What went wrong** (error message, unexpected behavior, incorrect data)
4. **Screenshot** (if possible) - Press F12 → Console tab for technical errors
5. **URL** of the exact page you were testing
6. **Browser details** (Chrome version - go to `chrome://version/`)

### How to Report

Send your feedback to: **[Your Email/Contact]**

Or create an issue with this template:
```
**Tester ID**: [Your ID]
**Feature**: [Show Details / Summarize / Sidebar Toggle / etc.]
**Issue**: [Brief description]

**Steps to Reproduce**:
1. [Step 1]
2. [Step 2]
3. [Step 3]

**Expected Behavior**: [What should happen]
**Actual Behavior**: [What actually happened]

**Screenshot**: [Attach if available]
**URL**: [Bhulekh page URL]
**Chrome Version**: [From chrome://version/]
```

### Viewing Technical Errors

If something isn't working:
1. Press `F12` to open Chrome DevTools
2. Click the **Console** tab
3. Look for red error messages
4. Take a screenshot and include in your bug report

---

## Tips for Effective Testing

### 1. Test Different Pages
- Try various districts: Khordha, Cuttack, Puri, etc.
- Try various tehsils and villages
- Try different types of land records (agricultural, residential)
- Try pages with multiple owners vs. single owner

### 2. Test Edge Cases
- Very long documents (10+ plots)
- Special characters in names (apostrophes, hyphens)
- Missing information (incomplete records)
- Different RoR types (SRoR vs CRoR)

### 3. Use Feedback Buttons Frequently
- Mark extractions as **Correct** when accurate
- Mark as **Wrong** when you spot errors
- **Add comments** to describe what's wrong
- This data is invaluable for improving the AI!

### 4. Test Caching
- Click "Show Details" twice → Second click should be instant
- Click "Summarize" twice → Second click should show cache indicator
- Wait 24+ hours and test again → Should regenerate (no cache)

### 5. Test Keyboard Shortcut
- Press `Ctrl+Shift+B` multiple times
- Verify sidebar toggles smoothly
- Test on both Windows and Mac (if you have both)
- Check for shortcut conflicts: `chrome://extensions/shortcuts`

### 6. Note Loading Times
- First request: Measure time (should be 15-30 seconds)
- Second request: Should be faster (5-10 seconds)
- Cached request: Should be instant (< 1 second)
- Report if times are significantly longer

### 7. Verify All Extracted Fields
Don't just check district/village - verify:
- Owner name spelling
- Father's name spelling
- Plot numbers (all of them)
- Area amounts and units
- Land type classification

---

## FAQ

### Q: Why does the first request take so long?
**A**: The AWS Lambda function needs to "warm up" on first use (cold start). The container needs to load, which takes 15-30 seconds. Subsequent requests use the warm container and are much faster (5-10 seconds).

### Q: What's the difference between "Show Details" and "Summarize"?
**A**:
- **Show Details** = Structured extraction of raw data (district, owner, plots, etc.)
- **Summarize** = Comprehensive analysis with safety score, risk assessment, and recommendations

Think of "Show Details" as extracting facts, and "Summarize" as analyzing what those facts mean.

### Q: Can I change my Tester ID?
**A**: Currently, you need to clear extension storage to change it:
1. Go to `chrome://extensions/`
2. Find "Bhulekha Content Reader"
3. Click "Details"
4. Scroll down to "Remove extension"
5. Reinstall and enter new Tester ID

(Future update will add a settings UI)

### Q: Does this work offline?
**A**: No, it requires an internet connection to communicate with the AI API hosted on AWS Lambda.

### Q: How do I know if data is cached?
**A**:
- **Show Details**: Second click loads instantly (no loading spinner)
- **Summarize**: Shows "📦 Cached summary (loaded from database)" tag at top

### Q: What happens after 24 hours?
**A**: The cache expires. Next time you click the button, the AI will reprocess the page (fresh analysis).

### Q: Why does the sidebar block part of the webpage?
**A**: You can hide the sidebar to view the full webpage:
- Press `Ctrl+Shift+B` to hide
- Click the 🌾 floating button to hide
- View the webpage content
- Press `Ctrl+Shift+B` again to bring sidebar back

### Q: What data is collected?
**A**: We collect:
- Your Tester ID (anonymous identifier you chose)
- Which features you use (tracked in CloudWatch logs)
- Feedback on extraction accuracy (when you click thumbs up/down)
- Optional comments when you provide them
- Extracted data and summaries (stored in Supabase)

We do **NOT** collect:
- Personal information beyond your chosen tester ID
- Browsing history on other sites
- Data from other Chrome tabs

### Q: Why does it need "storage" permission?
**A**: To save your Tester ID in Chrome Sync so you don't have to enter it every time. Your ID syncs across your Chrome devices.

### Q: Why does it need "scripting" permission?
**A**: To read the Bhulekh webpage content and inject the sidebar. It only works on Bhulekh URLs.

### Q: Can I use this on other land record websites?
**A**: Not yet. Currently restricted to:
- `https://bhulekh.ori.nic.in/SRoRFront_Uni.aspx`
- `https://bhulekh.ori.nic.in/CRoRFront_Uni.aspx`

Future versions may support other websites.

---

## Technical Details (For Curious Testers)

### Extension Architecture
- **Type**: Chrome Extension Manifest V3
- **Language**: TypeScript compiled to JavaScript
- **Interface**: IFrame-based sidebar injection
- **Keyboard Shortcuts**: Chrome Commands API
- **Storage**: Chrome Sync Storage API

### Backend Stack
- **API**: FastAPI + Mangum (AWS Lambda adapter)
- **AI Model**: Claude 3.5 Sonnet (`claude-3-5-sonnet-20241022`) by Anthropic
- **Prompting Framework**: DSPy for programmable prompts
- **Database**: Supabase (PostgreSQL)
- **Hosting**: AWS Lambda (ap-south-1 - Mumbai region)
- **Container**: Docker (2048MB memory, 300s timeout)
- **Region**: ap-south-1 (Mumbai) for lower latency in India

### Data Flow
1. You open Bhulekh page → Sidebar auto-opens
2. Extension reads page content (text + HTML)
3. Sends to AWS Lambda API (`/load-content`, `/explain`)
4. Lambda calls Claude AI with DSPy prompts
5. AI analyzes and extracts data
6. Lambda stores in Supabase (PostgreSQL)
7. Response sent back to extension
8. Sidebar displays results
9. Second request → Loads from Supabase cache (no AI call)

### Caching Strategy
- **Page Context**: Stored in `page_contexts` table (upsert by URL)
- **Extractions**: Stored in `khatiyan_extractions` table (24-hour TTL)
- **Summaries**: Stored in `khatiyan_extractions` table (24-hour TTL)
- **Cache Key**: Based on (district, tehsil, village, khatiyan_number)
- **Cache Invalidation**: 24 hours from creation timestamp

---

## Troubleshooting

### Sidebar Not Appearing
1. Ensure you're on a supported URL (SRoRFront_Uni.aspx or CRoRFront_Uni.aspx)
2. Try the keyboard shortcut: `Ctrl+Shift+B`
3. Click the 🌾 floating button in bottom-right
4. Reload the page
5. Check Chrome console (F12 → Console) for errors

### Keyboard Shortcut Not Working
1. Go to `chrome://extensions/shortcuts`
2. Check if `Ctrl+Shift+B` is assigned to "Bhulekha Content Reader"
3. If there's a conflict, change the shortcut
4. Ensure the webpage has focus (click on page first)

### Loading Spinner Stuck
1. Wait 30 seconds (cold start can be slow)
2. Check your internet connection
3. Reload the page and try again
4. Check Chrome console (F12) for errors
5. Report if issue persists

### Feedback Not Submitting
1. Check that you have a tester ID set (not "anonymous")
2. Check your internet connection
3. Look for error messages in Chrome console (F12)
4. Try reloading the page
5. Report the issue with console screenshot

### Cache Not Working
1. Ensure you're testing the exact same page (same khatiyan)
2. Check if 24 hours have passed (cache expires)
3. Look for cache indicators ("📦 Cached summary")
4. Report if second click still shows loading spinner

### Extension Disappeared
1. Go to `chrome://extensions/`
2. Check if "Bhulekha Content Reader" is enabled
3. If missing, reinstall from .zip file
4. Check if Chrome updated (may disable developer extensions)

---

## Support

If you encounter any issues or have questions:
- **Email**: [Your Email]
- **GitHub Issues**: [Repository URL]
- **CloudWatch Logs**: Admins can view logs in real-time

Your reports are monitored and tracked with your Tester ID, so we can follow up on specific issues.

---

**Thank you for helping us improve the Bhulekha Extension!** 🙏

Your feedback is invaluable in making this tool better for everyone. We're using your input to:
- Improve AI accuracy
- Fix bugs and usability issues
- Optimize performance
- Add new features based on user needs

**Happy Testing!** 🌾

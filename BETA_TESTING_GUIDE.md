# Bhulekha Extension - Beta Testing Guide

## Overview

Thank you for participating in the Bhulekha Chrome Extension beta test! This extension helps you understand and extract information from Bhulekh land records.

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

### Step 3: First-Time Setup

1. Click the Bhulekha extension icon in your toolbar
2. A welcome popup will appear asking for your **Tester ID**
3. Enter your assigned tester ID or create one (examples: `Tester_Alice`, `John_Doe`, `Beta_User_1`)
4. Click **"Save & Continue"**
5. Your ID is saved and you won't be asked again

**Note**: Your tester ID helps us track usage patterns and feedback. Only use letters, numbers, underscores, and hyphens.

---

## How to Use the Extension

### 1. Navigate to Bhulekh Website

The extension only works on:
- `https://bhulekh.ori.nic.in/SRoRFront_Uni.aspx`
- `https://bhulekh.ori.nic.in/CRoRFront_Uni.aspx`

### 2. Load a Land Record

Once you're on a Khatiyan/RoR page:
1. Click the extension icon
2. Click **"Help me understand"** button
3. Wait for AI to analyze the page (5-10 seconds)
4. The extension will show:
   - A simple explanation of the document
   - Action buttons for quick tasks

### 3. Features to Test

#### Extract Details
- Click **"Extract Details"** button
- View structured information:
  - Location (District, Tehsil, Village, Khatiyan Number)
  - Owner details (Name, Father's name, Caste)
  - Plot information (Total plots, Area, Land type)
  - Special comments

#### Summarize
- Click the **"📝 Summarize"** button
- Get a comprehensive RoR summary with:
  - Safety score (1-10) with color-coded risk assessment
  - Plot details and ownership classification
  - Risk analysis
  - Recommended next steps

#### Ask Questions
- Type questions in the chat box
- Examples:
  - "What is the total area of land?"
  - "Who are the owners?"
  - "What type of land is this?"
  - "Are there any special comments?"

#### Submit Feedback
- After viewing extracted details, use the feedback buttons:
  - **👍 Correct** - If extraction is accurate
  - **👎 Wrong** - If extraction has errors
- This helps us improve the AI model!

---

## What to Test

Please test ALL features and report:

### 1. Installation & Setup
- [ ] Extension installs successfully
- [ ] Tester ID modal appears on first use
- [ ] Tester ID saves correctly (doesn't ask again)

### 2. Core Features
- [ ] "Help me understand" loads and explains content
- [ ] "Extract Details" shows structured data accurately
- [ ] "Summarize" generates RoR summary with risk assessment
- [ ] Chat responds to questions correctly

### 3. Accuracy
- [ ] Extracted location details are correct
- [ ] Owner information is accurate
- [ ] Plot numbers and areas match the document
- [ ] Summary risk assessment makes sense

### 4. User Experience
- [ ] Extension is easy to use
- [ ] Loading times are acceptable (5-30 seconds for AI)
- [ ] Error messages are clear
- [ ] Interface is intuitive

---

## Known Limitations

- **First request takes longer** (cold start): 20-30 seconds
- **Subsequent requests are faster**: 5-10 seconds
- **Only works on Bhulekh website**: Won't work on other sites
- **Requires internet connection**: Uses cloud AI services

---

## Reporting Issues

### When You Find a Bug

Please provide:
1. **Your Tester ID**
2. **What you were doing** (which feature/button)
3. **What went wrong** (error message, unexpected behavior)
4. **Screenshot** (if possible)
5. **URL** of the page you were testing

### How to Report

Send your feedback to: **[Your Email/Contact]**

Or create an issue with template:
```
**Tester ID**: [Your ID]
**Feature**: [Extract Details / Summarize / Chat / etc.]
**Issue**: [Description of problem]
**Steps to Reproduce**:
1. [Step 1]
2. [Step 2]
**Expected**: [What should happen]
**Actual**: [What actually happened]
```

---

## Tips for Effective Testing

1. **Test different Khatiyan pages** - Try various districts, villages
2. **Try edge cases** - Very long content, multiple owners, special characters
3. **Use the feedback buttons** - Mark extractions as correct/wrong
4. **Ask varied questions** - Test the chat with different query types
5. **Note loading times** - First request vs. subsequent requests
6. **Check all fields** - Verify every extracted field for accuracy

---

## FAQ

### Q: Why does the first request take so long?
**A**: The cloud AI service needs to "warm up" on first use (cold start). Subsequent requests are much faster.

### Q: Can I change my Tester ID?
**A**: Currently no, but you can clear extension data in `chrome://extensions` and reinstall to set a new ID.

### Q: Does this work offline?
**A**: No, it requires internet connection to communicate with the AI API.

### Q: What data is collected?
**A**: We collect:
- Your Tester ID (anonymous identifier you chose)
- Which features you use
- Feedback on extraction accuracy (when you click thumbs up/down)
- We do NOT collect personal information or browse your other tabs

### Q: Why does it need "storage" permission?
**A**: To save your Tester ID so you don't have to enter it every time.

---

## Technical Details (For Developers)

- **Backend**: AWS Lambda + FastAPI + Claude AI (Anthropic)
- **Database**: Supabase (PostgreSQL)
- **AI Model**: Claude 3.5 Sonnet with DSPy prompting framework
- **Architecture**: Serverless container deployment

---

## Support

If you encounter any issues or have questions:
- Email: **[Your Email]**
- GitHub Issues: **[Repository URL]**

---

**Thank you for helping us improve the Bhulekha Extension!** 🙏

Your feedback is invaluable in making this tool better for everyone.

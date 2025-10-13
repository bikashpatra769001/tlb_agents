# Bhulekha Extension - Distribution Package

## Package Contents

This beta testing package contains:

1. **bhulekha-extension-v1.0.zip** - The Chrome extension (13KB)
2. **BETA_TESTING_GUIDE.md** - Complete instructions for beta testers
3. **DISTRIBUTION_README.md** - This file

---

## For Beta Testers

**Quick Start:**
1. Download `bhulekha-extension-v1.0.zip`
2. Open Chrome → `chrome://extensions/`
3. Enable "Developer mode"
4. Drag and drop the .zip file onto the page
5. Enter your tester ID when prompted
6. Navigate to https://bhulekh.ori.nic.in/SRoRFront_Uni.aspx
7. Click the extension icon and start testing!

**Full instructions**: See `BETA_TESTING_GUIDE.md`

---

## For Administrators

### Extension Details

- **Name**: Bhulekha Content Reader
- **Version**: 1.0
- **Extension ID**: `hknfgjmgpcdehabepbgifofnglkiihgb`
- **Type**: Manifest V3 Chrome Extension
- **Size**: 13KB (packaged)

### Technical Stack

**Frontend (Chrome Extension)**:
- TypeScript → JavaScript (compiled)
- Chrome Extensions Manifest V3
- Chrome Storage API for tester ID persistence
- Fetch API for backend communication

**Backend (AWS Lambda)**:
- FastAPI + Mangum adapter
- Claude 3.5 Sonnet (Anthropic AI)
- DSPy for programmable prompting
- Supabase (PostgreSQL) for data storage
- Docker container deployment (2048MB memory, 300s timeout)

**Infrastructure**:
- AWS Lambda (us-east-1)
- Amazon ECR (Container Registry)
- API Gateway HTTP API
- CloudWatch Logs
- Function URL: `https://9tzh9wd092.execute-api.us-east-1.amazonaws.com`

### Tester Tracking

**How It Works**:
- Each tester sets an identifier on first use (e.g., `Tester_Alice`)
- ID is stored in Chrome Sync Storage (persistent)
- All API requests include `X-Tester-ID` header
- Backend logs tester ID for every endpoint call
- Supabase tracks which tester submitted feedback

**View Logs**:
```bash
aws logs tail /aws/lambda/bhulekha-extension-api --region us-east-1 --follow
```

Example log entries:
```
📥 [Tester: Tester_Alice] /load-content from https://bhulekh.ori.nic.in/...
💡 [Tester: Tester_Alice] /explain for https://bhulekh.ori.nic.in/...
👍👎 [Tester: Tester_Bob] /submit-feedback: correct for extraction 42
```

### CORS Security

**Production Mode** (currently active):
- CORS restricted to extension ID: `hknfgjmgpcdehabepbgifofnglkiihgb`
- Only THIS packaged extension can call the API
- All beta testers share the same extension ID (same package)

**Adding More Extension IDs** (if needed):
```bash
# Update Lambda environment variable with comma-separated IDs
aws lambda update-function-configuration \
  --function-name bhulekha-extension-api \
  --environment Variables="{...,CHROME_EXTENSION_ID=id1,id2,id3}" \
  --region us-east-1
```

### Distributing to New Testers

**Option 1: Same Package (Recommended)**
- Share `bhulekha-extension-v1.0.zip` with new testers
- All testers use the same extension ID
- No Lambda configuration needed
- Track testers by their self-chosen ID

**Option 2: Create Multiple IDs**
- Each tester loads unpacked extension (gets unique ID)
- Collect all IDs from testers
- Add all IDs to Lambda `CHROME_EXTENSION_ID` (comma-separated)

---

## Deployment Information

### Current Deployment

- **Status**: ✅ Production ready
- **Region**: us-east-1
- **API Endpoint**: https://9tzh9wd092.execute-api.us-east-1.amazonaws.com
- **Extension ID**: hknfgjmgpcdehabepbgifofnglkiihgb
- **Lambda Function**: bhulekha-extension-api
- **Container Image**: 292814267481.dkr.ecr.us-east-1.amazonaws.com/bhulekha-extension-api:latest
- **Last Updated**: 2025-10-13

### Cost Estimate (Monthly)

- **Lambda**: ~$3.60 (1000 requests, 8s avg execution)
- **API Gateway**: ~$0.01 (1000 requests)
- **ECR Storage**: ~$0.10 (container image storage)
- **Total**: ~$3.71/month

With beta testing (assume 5 testers, 50 requests each):
- **Monthly Cost**: ~$18 (escalated usage)

### Updating the Extension

If you make changes to the extension:

```bash
# 1. Update code in chrome-extension/src/
# 2. Rebuild TypeScript
cd chrome-extension && npm run build

# 3. Repackage
zip -r ../bhulekha-extension-v1.1.zip . -x "*.git*" -x "*node_modules*" -x "*.DS_Store" -x "src/*" -x "tsconfig.json" -x "package*.json"

# 4. Distribute new package to testers
# Note: Extension ID will change if you repackage!
```

### Updating the Backend

If you make changes to api_server.py:

```bash
# 1. Update code in api_server.py or prompts/

# 2. Rebuild Docker image
docker build --platform linux/amd64 -t bhulekha-extension-api:latest .

# 3. Push to ECR
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin 292814267481.dkr.ecr.us-east-1.amazonaws.com
docker tag bhulekha-extension-api:latest 292814267481.dkr.ecr.us-east-1.amazonaws.com/bhulekha-extension-api:latest
docker push 292814267481.dkr.ecr.us-east-1.amazonaws.com/bhulekha-extension-api:latest

# 4. Update Lambda
aws lambda update-function-code \
  --function-name bhulekha-extension-api \
  --image-uri 292814267481.dkr.ecr.us-east-1.amazonaws.com/bhulekha-extension-api:latest \
  --region us-east-1

# 5. Wait for update
aws lambda wait function-updated --function-name bhulekha-extension-api --region us-east-1
```

---

## Monitoring

### View Real-Time Logs

```bash
aws logs tail /aws/lambda/bhulekha-extension-api --region us-east-1 --follow
```

### Check Lambda Status

```bash
aws lambda get-function --function-name bhulekha-extension-api --region us-east-1
```

### Test Health Endpoint

```bash
curl https://9tzh9wd092.execute-api.us-east-1.amazonaws.com/health
# Expected: {"status":"healthy"}
```

---

## Troubleshooting

### Extension Not Loading
- Ensure Developer Mode is enabled in `chrome://extensions/`
- Check that .zip file is not corrupted
- Try reloading the extension

### API Not Responding
- Check Lambda function status (may be in cold start)
- View CloudWatch logs for errors
- Verify API Gateway is configured correctly

### CORS Errors
- Verify extension ID matches Lambda environment variable
- Check Chrome DevTools Console for specific CORS error
- Ensure `ENVIRONMENT=production` in Lambda

### Tester ID Not Saving
- Check extension has "storage" permission in manifest
- Clear extension data and reinstall
- Check Chrome Sync is enabled

---

## Support Contacts

- **Technical Issues**: [Your Email]
- **AWS/Lambda Issues**: [Your Email]
- **Extension Distribution**: [Your Email]

---

## File Structure

```
bhulekha_extension/tlb_agents/
├── bhulekha-extension-v1.0.zip     # Packaged extension
├── BETA_TESTING_GUIDE.md            # For beta testers
├── DISTRIBUTION_README.md           # This file
├── api_server.py                    # Backend code
├── Dockerfile                       # Container definition
├── deploy-container.sh              # Deployment script
├── api-gateway-info.txt             # API details
├── chrome-extension/                # Extension source
│   ├── src/popup.ts                 # TypeScript source
│   ├── dist/popup.js                # Compiled JavaScript
│   ├── manifest.json                # Extension manifest
│   └── ...
└── ...
```

---

**Generated**: 2025-10-13
**Version**: 1.0

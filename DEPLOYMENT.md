# AWS Lambda Deployment Guide

## Overview

This guide walks through deploying the Bhulekh Chrome Extension FastAPI backend to AWS Lambda, enabling the Chrome extension to work without running a local server.

## Architecture

### Current (Local Development)
```
Chrome Extension → localhost:8000 (uvicorn) → Supabase
                                            → Anthropic Claude API
```

### Target (AWS Production)
```
Chrome Extension → API Gateway → Lambda Function → Supabase
                                                 → Anthropic Claude API
                                                 → CloudWatch Logs
```

## Prerequisites

- AWS Account with appropriate permissions
- AWS CLI installed and configured (`aws configure`)
- Python 3.12+ installed locally
- Existing Supabase project (URL and API key)
- Anthropic API key

## Phase 1: Code Preparation

### Step 1: Add Mangum Dependency

Mangum is an adapter that allows FastAPI to run on AWS Lambda.

Add to `pyproject.toml`:
```toml
dependencies = [
    # ... existing dependencies
    "mangum>=0.17.0",
]
```

Run:
```bash
uv sync
```

### Step 2: Migrate Chat Context Storage to Supabase

**Current Issue**: The `page_contexts` dictionary (api_server.py:27) is stored in-memory and will be lost between Lambda invocations.

**Solution**: Create a Supabase table for session storage.

Add to `schema.sql`:
```sql
-- Table for storing chat session contexts
CREATE TABLE IF NOT EXISTS page_contexts (
    id SERIAL PRIMARY KEY,
    url TEXT NOT NULL,
    title TEXT NOT NULL,
    text_content TEXT NOT NULL,
    html_content TEXT,
    word_count INTEGER,
    char_count INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_accessed TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Index for fast URL lookups
CREATE INDEX IF NOT EXISTS idx_page_contexts_url ON page_contexts(url);

-- Clean up old contexts (older than 24 hours)
CREATE INDEX IF NOT EXISTS idx_page_contexts_created_at ON page_contexts(created_at);
```

**Update `api_server.py`** to replace in-memory storage:

Replace:
```python
page_contexts = {}  # Line 27
```

With Supabase-backed storage functions:
```python
async def store_page_context(url: str, title: str, text: str, html: str = None):
    """Store page context in Supabase"""
    if not supabase_client:
        return False

    try:
        data = {
            "url": url,
            "title": title,
            "text_content": text,
            "html_content": html,
            "word_count": len(text.split()),
            "char_count": len(text)
        }

        # Upsert: update if exists, insert if new
        result = supabase_client.table("page_contexts")\
            .upsert(data, on_conflict="url")\
            .execute()

        return True
    except Exception as e:
        print(f"Error storing page context: {e}")
        return False

async def get_page_context(url: str) -> dict:
    """Retrieve page context from Supabase"""
    if not supabase_client:
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

            return result.data[0]
        return None
    except Exception as e:
        print(f"Error retrieving page context: {e}")
        return None
```

Update `/load-content` endpoint (api_server.py:461):
```python
@app.post("/load-content")
async def load_content(webpage: WebpageContent):
    # ... existing validation code ...

    # Store content in Supabase instead of in-memory
    success = await store_page_context(
        url=webpage.url,
        title=webpage.title,
        text=text_content,
        html=html_content
    )

    if not success:
        raise HTTPException(status_code=500, detail="Failed to store content")

    return {
        "status": "success",
        "message": "Content loaded successfully",
        "word_count": len(text_content.split())
    }
```

Update `/chat` endpoint (api_server.py:501):
```python
@app.post("/chat")
async def chat_with_content(chat: ChatQuery):
    # ... existing validation code ...

    # Get stored content from Supabase
    page_data = await get_page_context(chat.url)

    if not page_data:
        raise HTTPException(status_code=404, detail="Page content not loaded. Please load the page first.")

    text_content = page_data["text_content"]
    # ... rest of the code ...
```

### Step 3: Create Lambda Handler

Add at the end of `api_server.py`:

```python
# ==================== Lambda Handler ====================

# Import Mangum for Lambda compatibility
try:
    from mangum import Mangum
    handler = Mangum(app, lifespan="off")
    print("✅ Lambda handler configured with Mangum")
except ImportError:
    print("⚠️  Mangum not installed - Lambda deployment not available")
    handler = None

# For local development, keep the uvicorn runner
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

### Step 4: Generate Requirements File

Create `requirements.txt` for Lambda packaging:

```bash
uv pip freeze > requirements.txt
```

Or manually create with exact versions:

```txt
fastapi==0.117.1
uvicorn==0.37.0
anthropic==0.68.1
dspy-ai==2.5.0
supabase==2.10.0
python-dotenv==1.1.1
mangum==0.17.0
pydantic==2.10.3
httpx==0.28.1
```

### Step 5: Update CORS Configuration

Update CORS settings in `api_server.py` for production:

```python
# Determine environment
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
CHROME_EXTENSION_ID = os.getenv("CHROME_EXTENSION_ID", "*")

if ENVIRONMENT == "production":
    # Restrict to Chrome extension origin
    allowed_origins = [
        f"chrome-extension://{CHROME_EXTENSION_ID}",
    ]
else:
    # Allow all for development
    allowed_origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

## Phase 2: AWS Infrastructure Setup

### Step 6: Create Lambda Function

#### Option A: AWS Console

1. Go to AWS Lambda Console: https://console.aws.amazon.com/lambda
2. Click "Create function"
3. Choose "Author from scratch"
4. Configure:
   - **Function name**: `bhulekha-extension-api`
   - **Runtime**: Python 3.12
   - **Architecture**: x86_64
   - **Execution role**: Create new role with basic Lambda permissions
5. Click "Create function"

#### Option B: AWS CLI

```bash
# Create execution role first
aws iam create-role \
  --role-name bhulekha-lambda-role \
  --assume-role-policy-document '{
    "Version": "2012-10-17",
    "Statement": [{
      "Effect": "Allow",
      "Principal": {"Service": "lambda.amazonaws.com"},
      "Action": "sts:AssumeRole"
    }]
  }'

# Attach basic execution policy
aws iam attach-role-policy \
  --role-name bhulekha-lambda-role \
  --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole

# Create Lambda function (deployment package created in Step 7)
aws lambda create-function \
  --function-name bhulekha-extension-api \
  --runtime python3.12 \
  --role arn:aws:iam::YOUR_ACCOUNT_ID:role/bhulekha-lambda-role \
  --handler lambda_function.handler \
  --timeout 300 \
  --memory-size 1024 \
  --zip-file fileb://deployment-package.zip
```

### Step 7: Build Deployment Package

Lambda deployment packages must include all dependencies. Due to size constraints, we'll use Lambda Layers for large dependencies.

#### Create Deployment Package

```bash
# Create deployment directory
mkdir -p lambda-deployment
cd lambda-deployment

# Copy application code
cp ../api_server.py .
cp -r ../prompts ./prompts  # Include prompt files

# Install dependencies to a 'python' directory (for Lambda layer)
mkdir -p layer/python
pip install -r ../requirements.txt -t layer/python/

# Create layer ZIP
cd layer
zip -r ../../lambda-layer.zip python/
cd ..

# Create function ZIP (just application code)
zip -r ../lambda-function.zip api_server.py prompts/

cd ..
```

#### Size Optimization

Lambda has size limits:
- **Deployment package (direct)**: 50 MB (zipped), 250 MB (unzipped)
- **With layers**: 250 MB (unzipped) total

If dependencies exceed limits, use layers:

```bash
# Publish layer
aws lambda publish-layer-version \
  --layer-name bhulekha-dependencies \
  --description "Dependencies for Bhulekha Extension API" \
  --zip-file fileb://lambda-layer.zip \
  --compatible-runtimes python3.12

# Note the LayerVersionArn from output

# Attach layer to function
aws lambda update-function-configuration \
  --function-name bhulekha-extension-api \
  --layers arn:aws:lambda:REGION:ACCOUNT_ID:layer:bhulekha-dependencies:VERSION
```

### Step 8: Configure Lambda Settings

```bash
# Set timeout (5 minutes for AI operations)
aws lambda update-function-configuration \
  --function-name bhulekha-extension-api \
  --timeout 300

# Set memory (1024 MB - 2048 MB for AI workloads)
aws lambda update-function-configuration \
  --function-name bhulekha-extension-api \
  --memory-size 1024

# Set environment variables
aws lambda update-function-configuration \
  --function-name bhulekha-extension-api \
  --environment Variables="{
    ANTHROPIC_API_KEY=your-key-here,
    SUPABASE_URL=https://your-project.supabase.co,
    SUPABASE_KEY=your-key-here,
    ENVIRONMENT=production
  }"
```

**Security Note**: For production, use AWS Secrets Manager instead of environment variables (see Step 9).

### Step 9: Set Up AWS Secrets Manager (Recommended)

Store sensitive credentials securely:

```bash
# Create secret for Anthropic API key
aws secretsmanager create-secret \
  --name bhulekha/anthropic-api-key \
  --secret-string "your-anthropic-key-here"

# Create secret for Supabase credentials
aws secretsmanager create-secret \
  --name bhulekha/supabase-credentials \
  --secret-string '{
    "url": "https://your-project.supabase.co",
    "key": "your-supabase-key"
  }'
```

**Update IAM role** to allow Secrets Manager access:

```bash
aws iam attach-role-policy \
  --role-name bhulekha-lambda-role \
  --policy-arn arn:aws:iam::aws:policy/SecretsManagerReadWrite
```

**Update `api_server.py`** to read from Secrets Manager:

```python
import boto3
import json

def get_secret(secret_name: str) -> dict:
    """Retrieve secret from AWS Secrets Manager"""
    try:
        client = boto3.client('secretsmanager')
        response = client.get_secret_value(SecretId=secret_name)
        return json.loads(response['SecretString'])
    except Exception as e:
        print(f"Error retrieving secret {secret_name}: {e}")
        return None

# Initialize clients with Secrets Manager in Lambda environment
if os.getenv("AWS_EXECUTION_ENV"):  # Running in Lambda
    # Get Anthropic API key
    anthropic_secret = get_secret("bhulekha/anthropic-api-key")
    api_key = anthropic_secret if isinstance(anthropic_secret, str) else None

    # Get Supabase credentials
    supabase_secret = get_secret("bhulekha/supabase-credentials")
    if supabase_secret:
        supabase_url = supabase_secret.get("url")
        supabase_key = supabase_secret.get("key")
else:  # Local development
    api_key = os.getenv("ANTHROPIC_API_KEY")
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_KEY")
```

### Step 10: Configure API Gateway

Create HTTP API (simpler and cheaper than REST API):

#### AWS Console

1. Go to API Gateway Console
2. Click "Create API"
3. Choose "HTTP API" → "Build"
4. Configure:
   - **API name**: `bhulekha-extension-api`
   - **Add integration**: Lambda
   - **Lambda function**: `bhulekha-extension-api`
   - **Version**: 2.0
5. Configure routes:
   - **Method**: ANY
   - **Resource path**: `/{proxy+}`
6. Configure CORS:
   - **Access-Control-Allow-Origin**: `chrome-extension://YOUR_EXTENSION_ID`
   - **Access-Control-Allow-Methods**: `GET, POST, OPTIONS`
   - **Access-Control-Allow-Headers**: `Content-Type`
7. Create and deploy

#### AWS CLI

```bash
# Create API Gateway
aws apigatewayv2 create-api \
  --name bhulekha-extension-api \
  --protocol-type HTTP \
  --target arn:aws:lambda:REGION:ACCOUNT_ID:function:bhulekha-extension-api

# Note the ApiId from output

# Create integration
aws apigatewayv2 create-integration \
  --api-id YOUR_API_ID \
  --integration-type AWS_PROXY \
  --integration-uri arn:aws:lambda:REGION:ACCOUNT_ID:function:bhulekha-extension-api \
  --payload-format-version 2.0

# Note the IntegrationId from output

# Create default route
aws apigatewayv2 create-route \
  --api-id YOUR_API_ID \
  --route-key '$default' \
  --target integrations/YOUR_INTEGRATION_ID

# Grant API Gateway permission to invoke Lambda
aws lambda add-permission \
  --function-name bhulekha-extension-api \
  --statement-id apigateway-invoke \
  --action lambda:InvokeFunction \
  --principal apigatewayv2.amazonaws.com \
  --source-arn "arn:aws:execute-api:REGION:ACCOUNT_ID:YOUR_API_ID/*/*"

# Create default stage (deploys automatically)
aws apigatewayv2 create-stage \
  --api-id YOUR_API_ID \
  --stage-name '$default' \
  --auto-deploy
```

**Your API URL will be**: `https://YOUR_API_ID.execute-api.REGION.amazonaws.com`

## Phase 3: Chrome Extension Update

### Step 11: Update Extension API Endpoint

Update `chrome-extension/src/popup.ts`:

Add a constant at the top:
```typescript
// API Configuration
const API_BASE_URL = process.env.API_URL || 'http://localhost:8000';

// Or hardcode for production:
const API_BASE_URL = 'https://YOUR_API_ID.execute-api.us-east-1.amazonaws.com';
```

Replace all fetch calls from:
```typescript
fetch('http://localhost:8000/endpoint', ...)
```

To:
```typescript
fetch(`${API_BASE_URL}/endpoint`, ...)
```

Update all endpoints:
- Line 259: `/summarize`
- Line 285: `/chat`
- Line 347: `/submit-feedback`
- Line 398: `/load-content`
- Line 417: `/explain`
- Line 470: `/get-extraction`
- Line 516: `/chat`

### Step 12: Rebuild Extension

```bash
cd chrome-extension
npm run build
```

### Step 13: Reload Extension in Chrome

1. Go to `chrome://extensions/`
2. Find your extension
3. Click reload icon
4. Test on a Bhulekh page

## Phase 4: Testing

### Step 14: Test All Endpoints

Test each endpoint with the Chrome extension:

1. Navigate to `https://bhulekh.ori.nic.in/SRoRFront_Uni.aspx`
2. Open extension popup
3. Test each feature:
   - Click "Help me understand" → Tests `/load-content` and `/explain`
   - Click "View Details" → Tests `/get-extraction`
   - Click "Summarize" → Tests `/summarize`
   - Submit feedback → Tests `/submit-feedback`
   - Ask a question → Tests `/chat`

### Step 15: Monitor CloudWatch Logs

```bash
# View latest logs
aws logs tail /aws/lambda/bhulekha-extension-api --follow

# Or use AWS Console:
# CloudWatch → Log groups → /aws/lambda/bhulekha-extension-api
```

Check for:
- Successful initialization messages
- API call durations
- Error messages
- Request/response payloads

## Phase 5: Production Optimizations

### Set Up CloudWatch Alarms

```bash
# Create alarm for errors
aws cloudwatch put-metric-alarm \
  --alarm-name bhulekha-api-errors \
  --alarm-description "Alert on Lambda errors" \
  --metric-name Errors \
  --namespace AWS/Lambda \
  --statistic Sum \
  --period 300 \
  --threshold 10 \
  --comparison-operator GreaterThanThreshold \
  --dimensions Name=FunctionName,Value=bhulekha-extension-api \
  --evaluation-periods 1

# Create alarm for duration
aws cloudwatch put-metric-alarm \
  --alarm-name bhulekha-api-slow-requests \
  --alarm-description "Alert on slow Lambda execution" \
  --metric-name Duration \
  --namespace AWS/Lambda \
  --statistic Average \
  --period 300 \
  --threshold 10000 \
  --comparison-operator GreaterThanThreshold \
  --dimensions Name=FunctionName,Value=bhulekha-extension-api \
  --evaluation-periods 2
```

### Clean Up Old Page Contexts

Create a scheduled Lambda function to clean up old page contexts (>24 hours):

```python
# cleanup_function.py
from supabase import create_client
import os

def handler(event, context):
    supabase_client = create_client(
        os.environ['SUPABASE_URL'],
        os.environ['SUPABASE_KEY']
    )

    # Delete contexts older than 24 hours
    result = supabase_client.table("page_contexts")\
        .delete()\
        .lt("created_at", "NOW() - INTERVAL '24 hours'")\
        .execute()

    print(f"Deleted {len(result.data)} old page contexts")
    return {"statusCode": 200, "body": "Cleanup complete"}
```

Schedule with EventBridge:
```bash
aws events put-rule \
  --name bhulekha-cleanup-daily \
  --schedule-expression "rate(1 day)"

aws events put-targets \
  --rule bhulekha-cleanup-daily \
  --targets Id=1,Arn=arn:aws:lambda:REGION:ACCOUNT_ID:function:bhulekha-cleanup
```

### Optimize Cold Start

Cold starts occur when Lambda initializes a new container. Optimize by:

1. **Use Provisioned Concurrency** (costs more but eliminates cold starts):
```bash
aws lambda put-provisioned-concurrency-config \
  --function-name bhulekha-extension-api \
  --provisioned-concurrent-executions 1 \
  --qualifier '$LATEST'
```

2. **Reduce package size**: Use layers for dependencies

3. **Lazy load imports**: Import heavy libraries inside functions, not at module level

## Deployment Script

Create `deploy.sh` for easy updates:

```bash
#!/bin/bash

echo "Building deployment package..."

# Navigate to project directory
cd "$(dirname "$0")"

# Install dependencies
uv sync

# Create deployment directory
rm -rf lambda-deployment
mkdir -p lambda-deployment

# Copy code
cp api_server.py lambda-deployment/
cp -r prompts lambda-deployment/

# Create ZIP
cd lambda-deployment
zip -r ../lambda-function.zip .
cd ..

# Update Lambda function
echo "Uploading to Lambda..."
aws lambda update-function-code \
  --function-name bhulekha-extension-api \
  --zip-file fileb://lambda-function.zip

echo "Deployment complete!"
echo "Check status: aws lambda get-function --function-name bhulekha-extension-api"
```

Make executable:
```bash
chmod +x deploy.sh
```

## Cost Estimates

Based on typical usage (1000 requests/day):

| Service | Usage | Cost/Month |
|---------|-------|------------|
| Lambda | 1000 req/day × 30 days × 2s avg × 1024 MB | ~$2.50 |
| API Gateway | 30,000 requests | ~$0.03 |
| CloudWatch Logs | ~500 MB/month | ~$0.25 |
| Secrets Manager | 2 secrets | ~$0.80 |
| **Total** | | **~$3.60/month** |

First 1 million Lambda requests per month are free (AWS Free Tier).

## Troubleshooting

### Issue: "Internal Server Error" from API Gateway

**Check**:
1. Lambda function logs in CloudWatch
2. Lambda execution role has correct permissions
3. API Gateway has permission to invoke Lambda

```bash
aws lambda add-permission \
  --function-name bhulekha-extension-api \
  --statement-id apigateway-invoke \
  --action lambda:InvokeFunction \
  --principal apigatewayv2.amazonaws.com
```

### Issue: "Module not found" error in Lambda

**Solution**: Ensure dependencies are in deployment package or layer:
```bash
pip install -r requirements.txt -t lambda-deployment/
```

### Issue: Timeout errors

**Solution**: Increase Lambda timeout:
```bash
aws lambda update-function-configuration \
  --function-name bhulekha-extension-api \
  --timeout 300
```

### Issue: CORS errors in browser

**Solution**: Update CORS in `api_server.py` to include Chrome extension origin:
```python
allow_origins=[f"chrome-extension://{CHROME_EXTENSION_ID}"]
```

## Rollback Plan

If deployment fails, rollback to local server:

1. In `popup.ts`, change API_BASE_URL back to `http://localhost:8000`
2. Rebuild extension: `npm run build`
3. Reload extension in Chrome
4. Start local API: `python api_server.py`

## Next Steps

After successful deployment:

1. Set up custom domain (optional): Use Route 53 + API Gateway custom domain
2. Add authentication: Implement API key validation
3. Set up CI/CD: Use GitHub Actions for automated deployments
4. Add rate limiting: Use API Gateway throttling
5. Implement caching: Use API Gateway caching for faster responses

## Resources

- [AWS Lambda Python Documentation](https://docs.aws.amazon.com/lambda/latest/dg/lambda-python.html)
- [Mangum Documentation](https://mangum.io/)
- [API Gateway HTTP API Documentation](https://docs.aws.amazon.com/apigateway/latest/developerguide/http-api.html)
- [AWS CLI Reference](https://docs.aws.amazon.com/cli/)
- [FastAPI Deployment Guide](https://fastapi.tiangolo.com/deployment/)

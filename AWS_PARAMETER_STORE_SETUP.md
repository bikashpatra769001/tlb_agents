# AWS Parameter Store Setup Guide

This guide explains how to set up AWS Systems Manager Parameter Store for managing API keys and secrets across your AWS services.

## Overview

This project uses AWS Parameter Store to centrally manage secrets with complete environment separation:

**Environment Structure:**
- `.env.dev` → Development secrets → `/dev/bhulekha-extension/*` in Parameter Store
- `.env.prod` → Production secrets → `/prod/bhulekha-extension/*` in Parameter Store
- `.env` → Local development fallback (not synced to AWS)

**Secrets managed:**
- Anthropic API Key
- Supabase credentials
- Chrome Extension ID
- Prompt Service URL

**Benefits:**
- ✅ Share secrets across multiple Lambda functions and AWS services
- ✅ Complete environment separation (dev/staging/prod)
- ✅ Free for standard parameters (up to 10,000)
- ✅ Automatic encryption with AWS KMS
- ✅ IAM-based access control
- ✅ Version history and audit trails via CloudTrail

## Quick Start

For a new AWS account deployment:

```bash
# 1. Configure AWS CLI
aws configure

# 2. Create environment-specific .env file
cp .env.example .env.prod
# Edit .env.prod with your production secrets

# 3. Sync secrets to Parameter Store
./sync-secrets-to-aws.sh prod

# 4. Deploy Lambda (automatically sets up IAM permissions)
./deploy-container.sh

# 5. Add Chrome Extension ID parameter (deployment-time configuration)
aws ssm put-parameter \
  --name "/prod/bhulekha-extension/chrome-extension-id" \
  --value "hknfgjmgpcdehabepbgifofnglkiihgb" \
  --type "String" \
  --description "Chrome Extension ID for CORS and tracking" \
  --region ap-south-1
```

That's it! Lambda will automatically fetch secrets from Parameter Store at runtime.

> **Note**: The Chrome Extension ID is added manually because it's a deployment-time configuration (not a secret in .env). You only need to set this once per environment.

## Deployment-Time Configuration Parameters

Some parameters are **deployment-time configurations** rather than secrets, so they're not stored in `.env` files:

### Chrome Extension ID

**Why manual?** The extension ID is generated when you package the Chrome extension and may vary between environments (dev vs prod packages).

**When to set:** After deploying the Lambda function and packaging the Chrome extension.

```bash
# Production environment
aws ssm put-parameter \
  --name "/prod/bhulekha-extension/chrome-extension-id" \
  --value "hknfgjmgpcdehabepbgifofnglkiihgb" \
  --type "String" \
  --description "Production Chrome Extension ID for CORS and tracking" \
  --region ap-south-1

# Development environment (if using unpacked extension)
aws ssm put-parameter \
  --name "/dev/bhulekha-extension/chrome-extension-id" \
  --value "your-dev-extension-id-here" \
  --type "String" \
  --description "Development Chrome Extension ID" \
  --region ap-south-1
```

**Finding your Extension ID:**
1. Load your extension in Chrome
2. Go to `chrome://extensions/`
3. Enable "Developer mode"
4. Copy the ID shown under your extension

If this parameter is missing, the Lambda logs will show:
```
⚠️  Parameter not found: /prod/bhulekha-extension/chrome-extension-id, using default
⚠️  Development mode - CORS allows all origins
```

## Step 1: Set Up Environment-Specific .env Files

Create separate .env files for each environment:

```bash
# Create environment-specific files from template
cp .env.example .env.dev
cp .env.example .env.prod

# Edit each file with environment-specific secrets
# .env.dev - Use development API keys, test databases, etc.
# .env.prod - Use production API keys, production databases, etc.
```

**Recommended structure**:
```
.env.example  # Template (committed to git)
.env.dev      # Development secrets (gitignored)
.env.prod     # Production secrets (gitignored)
.env          # Local development fallback (gitignored)
```

## Step 2: Sync .env to Parameter Store

### Using the Sync Script (Recommended)

The easiest way to sync your environment-specific .env file to AWS Parameter Store:

```bash
# Sync production secrets
./sync-secrets-to-aws.sh prod    # Reads .env.prod → /prod/bhulekha-extension/*

# Sync development secrets
./sync-secrets-to-aws.sh dev     # Reads .env.dev → /dev/bhulekha-extension/*
```

The script automatically:
- ✅ Reads the correct .env file (e.g., `.env.prod`)
- ✅ Encrypts sensitive keys (API keys, passwords) as SecureString
- ✅ Skips AWS credentials (not needed in Parameter Store)
- ✅ Creates/updates all parameters in one command

### Manual Creation (Alternative)

If you prefer to create parameters manually:

```bash
# Set your AWS region
export AWS_REGION=us-east-1

# Set your environment (prod, dev, staging, etc.)
export ENV=prod

# Create Anthropic API Key parameter
aws ssm put-parameter \
  --name "/${ENV}/bhulekha-extension/anthropic-key" \
  --description "Anthropic API Key for Claude" \
  --value "YOUR_ANTHROPIC_API_KEY_HERE" \
  --type "SecureString" \
  --region $AWS_REGION

# Create Supabase URL parameter
aws ssm put-parameter \
  --name "/${ENV}/bhulekha-extension/supabase-url" \
  --description "Supabase project URL" \
  --value "https://your-project.supabase.co" \
  --type "String" \
  --region $AWS_REGION

# Create Supabase Key parameter
aws ssm put-parameter \
  --name "/${ENV}/bhulekha-extension/supabase-key" \
  --description "Supabase anon/public key" \
  --value "YOUR_SUPABASE_KEY_HERE" \
  --type "SecureString" \
  --region $AWS_REGION

# Create Chrome Extension ID parameter
aws ssm put-parameter \
  --name "/${ENV}/bhulekha-extension/chrome-extension-id" \
  --description "Chrome Extension ID for CORS" \
  --value "hknfgjmgpcdehabepbgifofnglkiihgb" \
  --type "String" \
  --region $AWS_REGION

# Create Prompt Service URL parameter
aws ssm put-parameter \
  --name "/${ENV}/bhulekha-extension/prompt-service-url" \
  --description "Prompt service API endpoint" \
  --value "https://5rp9zvhds7.ap-south-1.awsapprunner.com" \
  --type "String" \
  --region $AWS_REGION
```

### Using AWS Console

1. Go to **AWS Systems Manager** → **Parameter Store**
2. Click **Create parameter**
3. Fill in:
   - **Name**: `/prod/bhulekha-extension/anthropic-key`
   - **Description**: `Anthropic API Key for Claude`
   - **Type**: `SecureString`
   - **KMS Key**: `alias/aws/ssm` (default)
   - **Value**: Your actual API key
4. Repeat for all other parameters

## Step 3: Verify Parameters

```bash
# List all parameters for your environment
aws ssm describe-parameters \
  --parameter-filters "Key=Name,Option=BeginsWith,Values=/${ENV}/bhulekha" \
  --region $AWS_REGION

# Get a specific parameter value (decrypted)
aws ssm get-parameter \
  --name "/${ENV}/bhulekha-extension/anthropic-key" \
  --with-decryption \
  --region $AWS_REGION \
  --query "Parameter.Value" \
  --output text
```

## Step 4: Deploy Lambda (Automated IAM Setup)

The `deploy-container.sh` script **automatically** attaches Parameter Store permissions when deploying:

```bash
./deploy-container.sh
```

This script handles:
- ✅ Creating IAM role with Parameter Store read access
- ✅ Building and pushing Docker container
- ✅ Deploying Lambda function
- ✅ Configuring API Gateway

**The IAM policy attachment is automatic** - no manual setup needed!

### Manual IAM Setup (Optional)

If you need to manually attach Parameter Store permissions:

#### Option A: Attach Managed Policy (Quick)

```bash
# Get your Lambda function's role name
LAMBDA_ROLE=$(aws lambda get-function \
  --function-name bhulekha-extension-api \
  --region $AWS_REGION \
  --query "Configuration.Role" \
  --output text | awk -F'/' '{print $NF}')

# Attach the SSMReadOnlyAccess policy
aws iam attach-role-policy \
  --role-name $LAMBDA_ROLE \
  --policy-arn arn:aws:iam::aws:policy/AmazonSSMReadOnlyAccess
```

⚠️ **Warning**: `AmazonSSMReadOnlyAccess` grants read access to ALL parameters. For production, use Option B below for least-privilege access.

#### Option B: Create Custom Policy (Recommended for Production)

Create a custom IAM policy that only grants access to your specific parameters:

```bash
# Create policy document
cat > ssm-policy.json <<'EOF'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "ReadBhulekhaParameters",
      "Effect": "Allow",
      "Action": [
        "ssm:GetParameter",
        "ssm:GetParameters",
        "ssm:GetParametersByPath"
      ],
      "Resource": [
        "arn:aws:ssm:us-east-1:*:parameter/prod/bhulekha-extension/*",
        "arn:aws:ssm:us-east-1:*:parameter/dev/bhulekha-extension/*"
      ]
    },
    {
      "Sid": "DecryptSecureStrings",
      "Effect": "Allow",
      "Action": [
        "kms:Decrypt"
      ],
      "Resource": "arn:aws:kms:us-east-1:*:key/*",
      "Condition": {
        "StringEquals": {
          "kms:ViaService": "ssm.us-east-1.amazonaws.com"
        }
      }
    }
  ]
}
EOF

# Create the policy
aws iam create-policy \
  --policy-name BhulekhaParameterStoreAccess \
  --policy-document file://ssm-policy.json \
  --description "Read access to Bhulekha Parameter Store parameters"

# Attach to Lambda role
aws iam attach-role-policy \
  --role-name $LAMBDA_ROLE \
  --policy-arn arn:aws:iam::$(aws sts get-caller-identity --query Account --output text):policy/BhulekhaParameterStoreAccess
```

## Step 5: Test the Integration

### Test locally with .env file

For local development, the code falls back to `.env` file if Parameter Store is not available:

```bash
# Your existing .env file still works
python api_server.py
```

### Test in Lambda

Check CloudWatch Logs for successful parameter retrieval:

```bash
aws logs tail /aws/lambda/bhulekha-extension-api --follow
```

You should see:
```
✅ Using environment variable ANTHROPIC_API_KEY for /prod/bhulekha-extension/anthropic-key
```
or
```
🔍 Fetching parameter from SSM: /prod/bhulekha-extension/anthropic-key
✅ Successfully retrieved parameter: /prod/bhulekha-extension/anthropic-key
```

## Updating Parameters

To update a parameter value:

```bash
aws ssm put-parameter \
  --name "/${ENV}/bhulekha-extension/anthropic-key" \
  --value "NEW_API_KEY_VALUE" \
  --type "SecureString" \
  --overwrite \
  --region $AWS_REGION
```

**Note**: Lambda containers cache the parameter values using `@lru_cache`. To force a refresh:
1. Wait for Lambda container to expire (after 15-30 minutes of inactivity)
2. Or redeploy the function to create new containers

## Multi-Environment Setup

To support multiple environments (dev, staging, prod):

```bash
# Development environment
aws ssm put-parameter \
  --name "/dev/bhulekha-extension/anthropic-key" \
  --value "DEV_API_KEY" \
  --type "SecureString"

# Production environment
aws ssm put-parameter \
  --name "/prod/bhulekha-extension/anthropic-key" \
  --value "PROD_API_KEY" \
  --type "SecureString"
```

Then set `ENVIRONMENT` env var in your Lambda:
- Dev Lambda: `ENVIRONMENT=dev`
- Prod Lambda: `ENVIRONMENT=prod`

## Sharing Parameters Across Services

Any AWS service (Lambda, ECS, EC2, App Runner) can use the same parameters:

1. **Deploy the `aws_secrets.py` utility** to each service
2. **Grant IAM permissions** to read Parameter Store
3. **Import and use**:
   ```python
   from aws_secrets import get_secrets
   secrets = get_secrets()
   api_key = secrets["anthropic_api_key"]
   ```

## Cost Estimate

- **Standard parameters**: FREE (up to 10,000 parameters)
- **API calls**: FREE (standard throughput)
- **Advanced parameters**: $0.05/month (not needed for this use case)

Total cost: **$0.00/month** 🎉

## Troubleshooting

### Error: "Parameter not found"
- Verify parameter name matches exactly (case-sensitive)
- Check region matches your Lambda region
- Run `aws ssm describe-parameters` to list all parameters

### Error: "Access Denied"
- Verify IAM role has `ssm:GetParameter` permission
- Check resource ARN matches your parameter path
- For SecureString, ensure `kms:Decrypt` permission exists

### Lambda uses old values
- Parameter cache persists for Lambda container lifetime
- Wait for container to expire, or redeploy Lambda function

### Local development not working
- Ensure `.env` file has the required keys
- The code automatically falls back to environment variables when not in Lambda

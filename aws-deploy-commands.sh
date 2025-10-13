#!/bin/bash

# ============================================================================
# AWS Lambda Deployment Commands - Audit Trail & Automation Script
# ============================================================================
# This script contains all AWS CLI commands executed for deploying
# the Bhulekha Extension API to AWS Lambda
#
# Usage:
#   1. Review and update the CONFIGURATION section below
#   2. Run: ./aws-deploy-commands.sh
#   3. Or execute commands manually one by one
#
# Created: 2025-10-13
# Account: 292814267481
# Region: us-east-1
# ============================================================================

set -e  # Exit on error

# ============================================================================
# CONFIGURATION
# ============================================================================

# AWS Configuration
AWS_ACCOUNT_ID="292814267481"
AWS_REGION="us-east-1"

# Lambda Configuration
FUNCTION_NAME="bhulekha-extension-api"
LAMBDA_ROLE_NAME="bhulekha-lambda-role"
LAMBDA_RUNTIME="python3.12"
LAMBDA_MEMORY="1024"
LAMBDA_TIMEOUT="300"
LAMBDA_HANDLER="api_server.handler"

# Environment Variables (FILL THESE IN BEFORE RUNNING)
ANTHROPIC_API_KEY="${ANTHROPIC_API_KEY:-your_anthropic_key_here}"
SUPABASE_URL="${SUPABASE_URL:-https://your-project.supabase.co}"
SUPABASE_KEY="${SUPABASE_KEY:-your_supabase_key_here}"
CHROME_EXTENSION_ID="${CHROME_EXTENSION_ID:-your_extension_id_here}"

# Deployment Package
DEPLOYMENT_DIR="lambda-deployment"
DEPLOYMENT_ZIP="lambda-function.zip"

echo "============================================================================"
echo "AWS Lambda Deployment Script"
echo "============================================================================"
echo "Account ID: $AWS_ACCOUNT_ID"
echo "Region: $AWS_REGION"
echo "Function: $FUNCTION_NAME"
echo "============================================================================"
echo

# ============================================================================
# STEP 1: Verify AWS CLI Configuration
# ============================================================================
echo "Step 1: Verifying AWS CLI configuration..."

# Get current AWS identity
aws sts get-caller-identity

# Get configured region
CURRENT_REGION=$(aws configure get region)
echo "Configured region: $CURRENT_REGION"

if [ "$CURRENT_REGION" != "$AWS_REGION" ]; then
    echo "⚠️  Warning: Configured region ($CURRENT_REGION) differs from target region ($AWS_REGION)"
    echo "   Update AWS_REGION variable or run: aws configure set region $AWS_REGION"
fi

echo "✅ Step 1 complete"
echo

# ============================================================================
# STEP 2: Create IAM Role for Lambda Execution
# ============================================================================
echo "Step 2: Creating IAM role for Lambda execution..."

# Check if role already exists
if aws iam get-role --role-name $LAMBDA_ROLE_NAME 2>/dev/null; then
    echo "⚠️  Role $LAMBDA_ROLE_NAME already exists, skipping creation"
else
    # Create IAM role with Lambda assume role policy
    aws iam create-role \
      --role-name $LAMBDA_ROLE_NAME \
      --assume-role-policy-document '{
        "Version": "2012-10-17",
        "Statement": [{
          "Effect": "Allow",
          "Principal": {"Service": "lambda.amazonaws.com"},
          "Action": "sts:AssumeRole"
        }]
      }'

    echo "✅ Created IAM role: $LAMBDA_ROLE_NAME"
fi

# Attach CloudWatch Logs policy for Lambda logging
aws iam attach-role-policy \
  --role-name $LAMBDA_ROLE_NAME \
  --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole

echo "✅ Attached CloudWatch Logs policy"

# Wait for role to propagate
echo "⏳ Waiting 10 seconds for IAM role to propagate..."
sleep 10

echo "✅ Step 2 complete"
echo

# ============================================================================
# STEP 3: Build Lambda Deployment Package
# ============================================================================
echo "Step 3: Building Lambda deployment package..."

# Clean up old deployment artifacts
rm -rf $DEPLOYMENT_DIR $DEPLOYMENT_ZIP

# Create deployment directory
mkdir -p $DEPLOYMENT_DIR

# Copy application code
cp api_server.py $DEPLOYMENT_DIR/
if [ -d "prompts" ]; then
    cp -r prompts $DEPLOYMENT_DIR/
    echo "  ✓ Copied prompts directory"
fi

# Install dependencies using uv
echo "  📦 Installing dependencies (this may take 1-2 minutes)..."
uv pip install -r requirements.txt --target $DEPLOYMENT_DIR/ --python-version 3.12

# Create deployment ZIP
cd $DEPLOYMENT_DIR
zip -r ../$DEPLOYMENT_ZIP . -q
cd ..

# Check ZIP size
ZIP_SIZE=$(du -h $DEPLOYMENT_ZIP | cut -f1)
echo "  📊 Deployment package size: $ZIP_SIZE"

# Check if package exceeds Lambda limit (50MB zipped, 250MB unzipped)
ZIP_SIZE_BYTES=$(stat -f%z $DEPLOYMENT_ZIP 2>/dev/null || stat -c%s $DEPLOYMENT_ZIP)
if [ $ZIP_SIZE_BYTES -gt 52428800 ]; then
    echo "  ⚠️  Warning: Package size exceeds 50MB. Consider using Lambda Layers."
    echo "     See DEPLOYMENT.md Step 7 for instructions."
fi

echo "✅ Step 3 complete"
echo

# ============================================================================
# STEP 4: Create Lambda Function
# ============================================================================
echo "Step 4: Creating Lambda function..."

# Check if function already exists
if aws lambda get-function --function-name $FUNCTION_NAME --region $AWS_REGION 2>/dev/null; then
    echo "⚠️  Function $FUNCTION_NAME already exists"
    echo "   Updating function code instead..."

    # Update existing function code
    aws lambda update-function-code \
      --function-name $FUNCTION_NAME \
      --zip-file fileb://$DEPLOYMENT_ZIP \
      --region $AWS_REGION

    echo "✅ Updated function code"
else
    # Create new Lambda function
    LAMBDA_ROLE_ARN="arn:aws:iam::$AWS_ACCOUNT_ID:role/$LAMBDA_ROLE_NAME"

    aws lambda create-function \
      --function-name $FUNCTION_NAME \
      --runtime $LAMBDA_RUNTIME \
      --role $LAMBDA_ROLE_ARN \
      --handler $LAMBDA_HANDLER \
      --timeout $LAMBDA_TIMEOUT \
      --memory-size $LAMBDA_MEMORY \
      --zip-file fileb://$DEPLOYMENT_ZIP \
      --region $AWS_REGION

    echo "✅ Created Lambda function: $FUNCTION_NAME"
fi

# Wait for function to be ready
echo "⏳ Waiting for function to be ready..."
aws lambda wait function-active \
  --function-name $FUNCTION_NAME \
  --region $AWS_REGION

echo "✅ Step 4 complete"
echo

# ============================================================================
# STEP 5: Configure Environment Variables
# ============================================================================
echo "Step 5: Configuring Lambda environment variables..."

# Check if environment variables are set
if [ "$ANTHROPIC_API_KEY" == "your_anthropic_key_here" ]; then
    echo "⚠️  Warning: ANTHROPIC_API_KEY not set"
    echo "   Set it in your environment or update this script"
fi

if [ "$SUPABASE_URL" == "https://your-project.supabase.co" ]; then
    echo "⚠️  Warning: SUPABASE_URL not set"
fi

# Update Lambda environment variables
aws lambda update-function-configuration \
  --function-name $FUNCTION_NAME \
  --environment Variables="{
    ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY,
    SUPABASE_URL=$SUPABASE_URL,
    SUPABASE_KEY=$SUPABASE_KEY,
    ENVIRONMENT=production,
    CHROME_EXTENSION_ID=$CHROME_EXTENSION_ID
  }" \
  --region $AWS_REGION

echo "✅ Environment variables configured"

# Wait for configuration update
aws lambda wait function-updated \
  --function-name $FUNCTION_NAME \
  --region $AWS_REGION

echo "✅ Step 5 complete"
echo

# ============================================================================
# STEP 6: Create API Gateway HTTP API
# ============================================================================
echo "Step 6: Creating API Gateway HTTP API..."

# Create API Gateway HTTP API with Lambda integration
API_RESPONSE=$(aws apigatewayv2 create-api \
  --name "$FUNCTION_NAME-api" \
  --protocol-type HTTP \
  --target "arn:aws:lambda:$AWS_REGION:$AWS_ACCOUNT_ID:function:$FUNCTION_NAME" \
  --region $AWS_REGION)

API_ID=$(echo $API_RESPONSE | grep -o '"ApiId":"[^"]*' | cut -d'"' -f4)
API_ENDPOINT=$(echo $API_RESPONSE | grep -o '"ApiEndpoint":"[^"]*' | cut -d'"' -f4)

echo "✅ Created API Gateway HTTP API"
echo "   API ID: $API_ID"
echo "   Endpoint: $API_ENDPOINT"

# Save API details to file for later reference
cat > api-gateway-info.txt <<EOF
API Gateway Information
=======================
API ID: $API_ID
API Endpoint: $API_ENDPOINT
Region: $AWS_REGION
Created: $(date)

Update your Chrome extension to use this endpoint:
const API_BASE_URL = '$API_ENDPOINT';
EOF

echo "   API details saved to: api-gateway-info.txt"
echo "✅ Step 6 complete"
echo

# ============================================================================
# STEP 7: Grant API Gateway Permission to Invoke Lambda
# ============================================================================
echo "Step 7: Granting API Gateway permission to invoke Lambda..."

# Add permission for API Gateway to invoke Lambda
aws lambda add-permission \
  --function-name $FUNCTION_NAME \
  --statement-id apigateway-invoke-$API_ID \
  --action lambda:InvokeFunction \
  --principal apigateway.amazonaws.com \
  --source-arn "arn:aws:execute-api:$AWS_REGION:$AWS_ACCOUNT_ID:$API_ID/*/*" \
  --region $AWS_REGION

echo "✅ API Gateway permission granted"
echo "✅ Step 7 complete"
echo

# ============================================================================
# DEPLOYMENT SUMMARY
# ============================================================================
echo "============================================================================"
echo "✅ DEPLOYMENT COMPLETE!"
echo "============================================================================"
echo
echo "Lambda Function:"
echo "  Name: $FUNCTION_NAME"
echo "  ARN: arn:aws:lambda:$AWS_REGION:$AWS_ACCOUNT_ID:function:$FUNCTION_NAME"
echo "  Handler: $LAMBDA_HANDLER"
echo "  Runtime: $LAMBDA_RUNTIME"
echo "  Memory: ${LAMBDA_MEMORY}MB"
echo "  Timeout: ${LAMBDA_TIMEOUT}s"
echo
echo "API Gateway:"
echo "  API ID: $API_ID"
echo "  Endpoint: $API_ENDPOINT"
echo
echo "Next Steps:"
echo "  1. Test the API:"
echo "     curl $API_ENDPOINT/health"
echo
echo "  2. View logs:"
echo "     aws logs tail /aws/lambda/$FUNCTION_NAME --region $AWS_REGION --follow"
echo
echo "  3. Update Chrome extension API endpoint in popup.ts:"
echo "     const API_BASE_URL = '$API_ENDPOINT';"
echo
echo "  4. Rebuild extension:"
echo "     cd chrome-extension && npm run build"
echo
echo "============================================================================"

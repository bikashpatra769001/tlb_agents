#!/bin/bash

# ============================================================================
# AWS Lambda Container Deployment Script
# ============================================================================
# Deploys FastAPI application as Lambda Container Image via Amazon ECR
#
# Prerequisites:
#   - Docker installed and running
#   - AWS CLI configured
#   - IAM role created (from previous script)
#
# Usage: ./deploy-container.sh
# ============================================================================

set -e  # Exit on error

# Configuration
AWS_ACCOUNT_ID="292814267481"
AWS_REGION="us-east-1"
FUNCTION_NAME="bhulekha-extension"
ECR_REPO_NAME="bhulekha-extension-api"
IMAGE_TAG="latest"
CHROME_EXTENSION_ID="hknfgjmgpcdehabepbgifofnglkiihgb"

# Load environment variables from .env if it exists
if [ -f .env ]; then
    echo "Loading environment variables from .env..."
    export $(grep -v '^#' .env | xargs)
fi

echo "============================================================================"
echo "AWS Lambda Container Deployment"
echo "============================================================================"
echo "Account: $AWS_ACCOUNT_ID"
echo "Region: $AWS_REGION"
echo "Function: $FUNCTION_NAME"
echo "ECR Repo: $ECR_REPO_NAME"
echo "============================================================================"
echo

# ============================================================================
# STEP 1: Check Docker
# ============================================================================
echo "Step 1: Checking Docker..."

if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed"
    echo "   Install from: https://www.docker.com/get-started"
    exit 1
fi

if ! docker info &> /dev/null; then
    echo "❌ Docker daemon is not running"
    echo "   Start Docker Desktop or run: sudo systemctl start docker"
    exit 1
fi

echo "✅ Docker is running"
echo

# ============================================================================
# STEP 2: Create ECR Repository
# ============================================================================
echo "Step 2: Creating ECR repository..."

# Check if repository exists
if aws ecr describe-repositories --repository-names $ECR_REPO_NAME --region $AWS_REGION &>/dev/null; then
    echo "⚠️  Repository $ECR_REPO_NAME already exists, using existing"
else
    # Create ECR repository
    aws ecr create-repository \
        --repository-name $ECR_REPO_NAME \
        --region $AWS_REGION \
        --image-scanning-configuration scanOnPush=true

    echo "✅ Created ECR repository: $ECR_REPO_NAME"
fi

ECR_REPO_URI="$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPO_NAME"
echo "   Repository URI: $ECR_REPO_URI"
echo

# ============================================================================
# STEP 3: Authenticate Docker to ECR
# ============================================================================
echo "Step 3: Authenticating Docker to ECR..."

aws ecr get-login-password --region $AWS_REGION | \
    docker login --username AWS --password-stdin $ECR_REPO_URI

echo "✅ Docker authenticated to ECR"
echo

# ============================================================================
# STEP 4: Build Docker Image
# ============================================================================
echo "Step 4: Building Docker image..."
echo "   This may take 5-10 minutes (installing dependencies)..."
echo

# Build for AMD64 architecture (Lambda uses x86_64)
docker build --platform linux/amd64 -t $ECR_REPO_NAME:$IMAGE_TAG .

echo "✅ Docker image built"
echo

# ============================================================================
# STEP 5: Tag and Push Image to ECR
# ============================================================================
echo "Step 5: Pushing image to ECR..."

docker tag $ECR_REPO_NAME:$IMAGE_TAG $ECR_REPO_URI:$IMAGE_TAG
docker push $ECR_REPO_URI:$IMAGE_TAG

echo "✅ Image pushed to ECR"
echo "   Image URI: $ECR_REPO_URI:$IMAGE_TAG"
echo

# ============================================================================
# STEP 6: Create or Update Lambda Function
# ============================================================================
echo "Step 6: Creating/updating Lambda function..."

LAMBDA_ROLE_ARN="arn:aws:iam::$AWS_ACCOUNT_ID:role/bhulekha-lambda-role"

# Check if function exists
if aws lambda get-function --function-name $FUNCTION_NAME --region $AWS_REGION &>/dev/null; then
    echo "⚠️  Function $FUNCTION_NAME already exists"
    echo "   Updating function code..."

    # Update existing function with new container image
    aws lambda update-function-code \
        --function-name $FUNCTION_NAME \
        --image-uri $ECR_REPO_URI:$IMAGE_TAG \
        --region $AWS_REGION

    echo "✅ Function code updated"
else
    # Create new Lambda function from container image
    aws lambda create-function \
        --function-name $FUNCTION_NAME \
        --package-type Image \
        --code ImageUri=$ECR_REPO_URI:$IMAGE_TAG \
        --role $LAMBDA_ROLE_ARN \
        --timeout 300 \
        --memory-size 2048 \
        --region $AWS_REGION

    echo "✅ Lambda function created"
fi

# Wait for function to be ready
echo "⏳ Waiting for function to be ready..."
aws lambda wait function-updated \
    --function-name $FUNCTION_NAME \
    --region $AWS_REGION

echo

# ============================================================================
# STEP 7: Configure Environment Variables
# ============================================================================
echo "Step 7: Configuring environment variables..."

# Check if environment variables are set
if [ -z "$ANTHROPIC_API_KEY" ]; then
    echo "⚠️  Warning: ANTHROPIC_API_KEY not set in environment"
fi

if [ -z "$SUPABASE_URL" ]; then
    echo "⚠️  Warning: SUPABASE_URL not set in environment"
fi

# Get Chrome extension ID
if [ -z "$CHROME_EXTENSION_ID" ]; then
    CHROME_EXTENSION_ID="your_extension_id_here"
    echo "⚠️  CHROME_EXTENSION_ID not set - using placeholder"
    echo "   Find your extension ID in chrome://extensions and update environment"
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

echo

# ============================================================================
# STEP 8: Create API Gateway (if not exists)
# ============================================================================
echo "Step 8: Setting up API Gateway..."

# Check if API already exists by function name
API_ID=$(aws apigatewayv2 get-apis --region $AWS_REGION \
    --query "Items[?Name=='$FUNCTION_NAME-api'].ApiId | [0]" \
    --output text)

if [ -z "$API_ID" ]; then
    echo "   Creating new API Gateway..."

    # Create API Gateway HTTP API with Lambda integration
    API_RESPONSE=$(aws apigatewayv2 create-api \
        --name "$FUNCTION_NAME-api" \
        --protocol-type HTTP \
        --target "arn:aws:lambda:$AWS_REGION:$AWS_ACCOUNT_ID:function:$FUNCTION_NAME" \
        --region $AWS_REGION)

    API_ID=$(echo $API_RESPONSE | grep -o '"ApiId":"[^"]*' | cut -d'"' -f4)
    API_ENDPOINT=$(echo $API_RESPONSE | grep -o '"ApiEndpoint":"[^"]*' | cut -d'"' -f4)

    echo "✅ Created API Gateway"
    echo "   API ID: $API_ID"
    echo "   Endpoint: $API_ENDPOINT"

    # Grant API Gateway permission to invoke Lambda
    aws lambda add-permission \
        --function-name $FUNCTION_NAME \
        --statement-id apigateway-invoke-$API_ID \
        --action lambda:InvokeFunction \
        --principal apigatewayv2.amazonaws.com \
        --source-arn "arn:aws:execute-api:$AWS_REGION:$AWS_ACCOUNT_ID:$API_ID/*/*" \
        --region $AWS_REGION

    echo "✅ API Gateway permission granted"

    # Save API details
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
else
    echo "⚠️  API Gateway already exists (ID: $API_ID)"
    API_ENDPOINT=$(aws apigatewayv2 get-api --api-id $API_ID --region $AWS_REGION \
        --query "ApiEndpoint" \
        --output text)
    echo "   Endpoint: $API_ENDPOINT"
fi

echo

# ============================================================================
# STEP 9: Configure CORS on API Gateway
# ============================================================================
echo "Step 9: Configuring CORS on API Gateway..."

# Note: API Gateway doesn't support chrome-extension:// origins, so we use wildcard (*)
# Security is still enforced by FastAPI in Lambda based on CHROME_EXTENSION_ID
aws apigatewayv2 update-api \
    --api-id $API_ID \
    --region $AWS_REGION \
    --cors-configuration "AllowOrigins=*,AllowMethods=GET,POST,OPTIONS,AllowHeaders=Content-Type,X-Tester-ID,AllowCredentials=false,MaxAge=3600"

echo "✅ CORS configured (API Gateway allows all origins, FastAPI restricts to extension ID)"
echo

# ============================================================================
# DEPLOYMENT SUMMARY
# ============================================================================
echo "============================================================================"
echo "✅ CONTAINER DEPLOYMENT COMPLETE!"
echo "============================================================================"
echo
echo "Lambda Function:"
echo "  Name: $FUNCTION_NAME"
echo "  Package: Container Image"
echo "  Image: $ECR_REPO_URI:$IMAGE_TAG"
echo "  Memory: 2048 MB"
echo "  Timeout: 300s"
echo
echo "API Gateway:"
echo "  API ID: $API_ID"
echo "  Endpoint: $API_ENDPOINT"
echo "  CORS: Enabled (wildcard at API Gateway, restricted by Lambda)"
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
echo "To update the function:"
echo "  ./deploy-container.sh"
echo
echo "============================================================================"

#!/bin/bash

# ============================================================================
# AWS Lambda Container Deployment Script
# ============================================================================
# Deploys FastAPI application as Lambda Container Image via Amazon ECR
#
# Prerequisites:
#   - Docker installed and running
#   - AWS CLI configured with appropriate credentials
#
# This script handles complete deployment including:
#   - IAM role creation (if not exists)
#   - ECR repository setup
#   - Docker image build and push
#   - Lambda function creation/update
#   - API Gateway configuration
#
# Usage: ./deploy-container.sh
# ============================================================================

set -e  # Exit on error

# Configuration
#AWS_ACCOUNT_ID="292814267481"
AWS_ACCOUNT_ID="293232900878"
AWS_REGION="ap-south-1"
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
# STEP 2: Create IAM Role for Lambda Execution
# ============================================================================
echo "Step 2: Creating IAM role for Lambda execution..."

# Check if role already exists
if aws iam get-role --role-name bhulekha-lambda-role 2>/dev/null; then
    echo "⚠️  Role bhulekha-lambda-role already exists, skipping creation"
else
    # Create IAM role with Lambda assume role policy
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

    echo "✅ Created IAM role: bhulekha-lambda-role"
fi

# Attach CloudWatch Logs policy for Lambda logging
aws iam attach-role-policy \
  --role-name bhulekha-lambda-role \
  --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole

echo "✅ Attached CloudWatch Logs policy"

# Attach SSM Parameter Store read access for secrets management
echo "   Attaching Parameter Store policy..."
aws iam attach-role-policy \
  --role-name bhulekha-lambda-role \
  --policy-arn arn:aws:iam::aws:policy/AmazonSSMReadOnlyAccess

echo "✅ Attached Parameter Store policy (for secrets management)"

# Wait for role to propagate
echo "⏳ Waiting 10 seconds for IAM role to propagate..."
sleep 10

echo "✅ Step 2 complete"
echo

# ============================================================================
# STEP 3: Create ECR Repository
# ============================================================================
echo "Step 3: Creating ECR repository..."

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
# STEP 4: Authenticate Docker to ECR
# ============================================================================
echo "Step 4: Authenticating Docker to ECR..."

aws ecr get-login-password --region $AWS_REGION | \
    docker login --username AWS --password-stdin $ECR_REPO_URI

echo "✅ Docker authenticated to ECR"
echo

# ============================================================================
# STEP 5: Build Docker Image
# ============================================================================
echo "Step 5: Building Docker image..."
echo "   This may take 5-10 minutes (installing dependencies)..."
echo

# Build for AMD64 architecture (Lambda uses x86_64)
docker build --platform linux/amd64 -t $ECR_REPO_NAME:$IMAGE_TAG .

echo "✅ Docker image built"
echo

# ============================================================================
# STEP 6: Tag and Push Image to ECR
# ============================================================================
echo "Step 6: Pushing image to ECR..."

docker tag $ECR_REPO_NAME:$IMAGE_TAG $ECR_REPO_URI:$IMAGE_TAG
docker push $ECR_REPO_URI:$IMAGE_TAG

echo "✅ Image pushed to ECR"
echo "   Image URI: $ECR_REPO_URI:$IMAGE_TAG"
echo

# ============================================================================
# STEP 7: Create or Update Lambda Function
# ============================================================================
echo "Step 7: Creating/updating Lambda function..."

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
# STEP 8: Configure Environment Variables
# ============================================================================
echo "Step 8: Configuring environment variables..."
echo
echo "📝 Note: Secrets are now managed in AWS Parameter Store"
echo "   Lambda will fetch secrets from: /prod/bhulekha-extension/*"
echo "   To sync .env.prod to Parameter Store, run: ./sync-secrets-to-aws.sh prod"
echo

# Determine environment (default to production for this region)
LAMBDA_ENVIRONMENT="prod"

# Update Lambda environment variables (only config, not secrets)
# Secrets are fetched from Parameter Store at runtime
# Note: AWS_REGION is automatically provided by Lambda, we don't need to set it
aws lambda update-function-configuration \
    --function-name $FUNCTION_NAME \
    --environment Variables="{
        ENVIRONMENT=$LAMBDA_ENVIRONMENT
    }" \
    --region $AWS_REGION

echo "✅ Environment variables configured"
echo "   ENVIRONMENT=$LAMBDA_ENVIRONMENT (determines Parameter Store path)"
echo "   AWS_REGION is automatically provided by Lambda"

# Wait for configuration update
aws lambda wait function-updated \
    --function-name $FUNCTION_NAME \
    --region $AWS_REGION

echo

# ============================================================================
# STEP 9: Create API Gateway (if not exists)
# ============================================================================
echo "Step 9: Setting up API Gateway..."

# Check if API already exists by function name
API_ID=$(aws apigatewayv2 get-apis --region $AWS_REGION \
    --query "Items[?Name=='$FUNCTION_NAME-api'].ApiId | [0]" \
    --output text)

# Check if API_ID is empty or "None" (AWS CLI returns "None" when no match found)
if [ -z "$API_ID" ] || [ "$API_ID" = "None" ]; then
    echo "   Creating new API Gateway..."

    # Create API Gateway HTTP API with Lambda integration
    # Note: Using --target auto-creates integration AND grants Lambda permissions
    # Use --query to extract ApiId and ApiEndpoint directly (cleaner than JSON parsing)
    read -r API_ID API_ENDPOINT < <(aws apigatewayv2 create-api \
        --name "$FUNCTION_NAME-api" \
        --protocol-type HTTP \
        --target "arn:aws:lambda:$AWS_REGION:$AWS_ACCOUNT_ID:function:$FUNCTION_NAME" \
        --region $AWS_REGION \
        --query '[ApiId, ApiEndpoint]' \
        --output text)

    echo "✅ Created API Gateway"
    echo "   API ID: $API_ID"
    echo "   Endpoint: $API_ENDPOINT"
    echo "   Lambda permissions automatically granted by --target parameter"

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
# STEP 10: Grant API Gateway Permission to Invoke Lambda
# ============================================================================
echo "Step 10: Granting API Gateway permission to invoke Lambda..."

# Check if permission already exists
if aws lambda get-policy --function-name $FUNCTION_NAME --region $AWS_REGION 2>/dev/null | grep -q "apigateway-invoke"; then
    echo "⚠️  Permission already exists, skipping"
else
    # Add permission for API Gateway to invoke Lambda
    aws lambda add-permission \
        --function-name $FUNCTION_NAME \
        --statement-id apigateway-invoke \
        --action lambda:InvokeFunction \
        --principal apigateway.amazonaws.com \
        --source-arn "arn:aws:execute-api:$AWS_REGION:$AWS_ACCOUNT_ID:$API_ID/*" \
        --region $AWS_REGION

    echo "✅ API Gateway permission granted"
fi

echo

# ============================================================================
# STEP 11: Configure CORS on API Gateway
# ============================================================================
echo "Step 11: Configuring CORS on API Gateway..."

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

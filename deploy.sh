#!/bin/bash

# AWS Lambda Deployment Script for Bhulekha Extension API
# This script packages and deploys the FastAPI application to AWS Lambda

set -e  # Exit on error

# Configuration
FUNCTION_NAME="bhulekha-extension-api"
REGION="${AWS_REGION:-us-east-1}"
DEPLOYMENT_DIR="lambda-deployment"

echo "========================================="
echo "AWS Lambda Deployment Script"
echo "Function: $FUNCTION_NAME"
echo "Region: $REGION"
echo "========================================="
echo

# Check if AWS CLI is installed
if ! command -v aws &> /dev/null; then
    echo "❌ Error: AWS CLI is not installed"
    echo "Install from: https://aws.amazon.com/cli/"
    exit 1
fi

# Check if AWS credentials are configured
if ! aws sts get-caller-identity &> /dev/null; then
    echo "❌ Error: AWS credentials not configured"
    echo "Run: aws configure"
    exit 1
fi

echo "✅ AWS CLI configured"
echo

# Clean up old deployment directory
echo "🧹 Cleaning up old deployment files..."
rm -rf $DEPLOYMENT_DIR
rm -f lambda-function.zip
echo

# Create deployment directory
echo "📁 Creating deployment directory..."
mkdir -p $DEPLOYMENT_DIR
echo

# Copy application code
echo "📋 Copying application code..."
cp api_server.py $DEPLOYMENT_DIR/
if [ -d "prompts" ]; then
    cp -r prompts $DEPLOYMENT_DIR/
    echo "  ✓ Copied prompts directory"
fi
echo "  ✓ Copied api_server.py"
echo

# Install dependencies
echo "📦 Installing dependencies..."
pip install -r requirements.txt -t $DEPLOYMENT_DIR/ --upgrade
echo "  ✓ Dependencies installed"
echo

# Create deployment ZIP
echo "🗜️  Creating deployment package..."
cd $DEPLOYMENT_DIR
zip -r ../lambda-function.zip . -q
cd ..
echo "  ✓ Created lambda-function.zip"
echo

# Get ZIP file size
ZIP_SIZE=$(du -h lambda-function.zip | cut -f1)
echo "📊 Deployment package size: $ZIP_SIZE"
echo

# Check if Lambda function exists
echo "🔍 Checking if Lambda function exists..."
if aws lambda get-function --function-name $FUNCTION_NAME --region $REGION &> /dev/null; then
    echo "  ✓ Function exists - updating code..."

    # Update function code
    aws lambda update-function-code \
        --function-name $FUNCTION_NAME \
        --zip-file fileb://lambda-function.zip \
        --region $REGION \
        --no-cli-pager

    echo "  ✓ Function code updated"
else
    echo "  ⚠️  Function does not exist"
    echo "     Create it first using AWS Console or:"
    echo "     See DEPLOYMENT.md for instructions"
    exit 1
fi

echo

# Wait for update to complete
echo "⏳ Waiting for function update to complete..."
aws lambda wait function-updated \
    --function-name $FUNCTION_NAME \
    --region $REGION

echo "  ✓ Update complete"
echo

# Get function info
echo "📋 Function Information:"
aws lambda get-function \
    --function-name $FUNCTION_NAME \
    --region $REGION \
    --query 'Configuration.[FunctionName,Runtime,MemorySize,Timeout,LastModified]' \
    --output table \
    --no-cli-pager

echo
echo "========================================="
echo "✅ Deployment Complete!"
echo "========================================="
echo
echo "Next steps:"
echo "1. Test the function: aws lambda invoke --function-name $FUNCTION_NAME --region $REGION response.json"
echo "2. Check logs: aws logs tail /aws/lambda/$FUNCTION_NAME --region $REGION --follow"
echo "3. Update Chrome extension API endpoint if needed"
echo

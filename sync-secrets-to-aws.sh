#!/bin/bash

# ============================================================================
# Sync .env Secrets to AWS Parameter Store
# ============================================================================
# Reads environment-specific .env file and syncs to AWS SSM Parameter Store
#
# File Structure:
#   .env.prod  → Production secrets (synced to /prod/bhulekha/*)
#   .env.dev   → Development secrets (synced to /dev/bhulekha/*)
#   .env       → Local development fallback (not synced)
#
# Prerequisites:
#   - AWS CLI configured with appropriate credentials
#   - Environment-specific .env file exists (e.g., .env.prod, .env.dev)
#
# Usage:
#   ./sync-secrets-to-aws.sh [environment]
#
# Examples:
#   ./sync-secrets-to-aws.sh prod     # Reads .env.prod → /prod/bhulekha/*
#   ./sync-secrets-to-aws.sh dev      # Reads .env.dev → /dev/bhulekha/*
# ============================================================================

set -e  # Exit on error

# Configuration
ENVIRONMENT="${1:-prod}"  # Default to 'prod' if not specified
AWS_REGION="${AWS_REGION:-ap-south-1}"  # Default region

# Determine which .env file to use based on environment
ENV_FILE=".env.${ENVIRONMENT}"

# Fall back to .env if environment-specific file doesn't exist
if [ ! -f "$ENV_FILE" ]; then
    echo "⚠️  Warning: $ENV_FILE not found, falling back to .env"
    ENV_FILE=".env"
fi

# Define which parameters should be SecureString (encrypted)
# All others will be stored as String type
SECURE_PARAMS=(
    "ANTHROPIC_API_KEY"
    "SUPABASE_KEY"
    "SUPABASE_ANON_KEY"
    "OPENAI_API_KEY"
    "DATABASE_PASSWORD"
)

# Parameters to skip (not needed in Parameter Store)
SKIP_PARAMS=(
    "AWS_ACCOUNT_ID"
    "AWS_REGION"
    "AWS_ACCESS_KEY_ID"
    "AWS_SECRET_ACCESS_KEY"
)

echo "============================================================================"
echo "Syncing Secrets to AWS Parameter Store"
echo "============================================================================"
echo "Environment: $ENVIRONMENT"
echo "Region: $AWS_REGION"
echo "Source: $ENV_FILE"
echo "Target Path: /$ENVIRONMENT/bhulekha-extension/"
echo "============================================================================"
echo

# Check if .env file exists
if [ ! -f "$ENV_FILE" ]; then
    echo "❌ Error: $ENV_FILE file not found"
    echo "   Create a .env file with your secrets first"
    exit 1
fi

# Check if AWS CLI is configured
if ! aws sts get-caller-identity &> /dev/null; then
    echo "❌ Error: AWS CLI not configured or credentials invalid"
    echo "   Run: aws configure"
    exit 1
fi

echo "✅ AWS CLI authenticated"
echo "   Account: $(aws sts get-caller-identity --query Account --output text)"
echo

# Function to check if a parameter should be secure
is_secure_param() {
    local param_name="$1"
    for secure in "${SECURE_PARAMS[@]}"; do
        if [[ "$param_name" == "$secure" ]]; then
            return 0  # True
        fi
    done
    return 1  # False
}

# Function to check if a parameter should be skipped
should_skip_param() {
    local param_name="$1"
    for skip in "${SKIP_PARAMS[@]}"; do
        if [[ "$param_name" == "$skip" ]]; then
            return 0  # True
        fi
    done
    return 1  # False
}

# Function to convert env var name to parameter name
# e.g., ANTHROPIC_API_KEY -> anthropic-key
env_to_param_name() {
    local env_name="$1"

    # Special case mappings for cleaner parameter names
    case "$env_name" in
        "ANTHROPIC_API_KEY")
            echo "anthropic-key"
            ;;
        "SUPABASE_URL")
            echo "supabase-url"
            ;;
        "SUPABASE_KEY"|"SUPABASE_ANON_KEY")
            echo "supabase-key"
            ;;
        "CHROME_EXTENSION_ID")
            echo "chrome-extension-id"
            ;;
        "PROMPT_SERVICE_URL")
            echo "prompt-service-url"
            ;;
        "PROMPT_CACHE_TTL_SECONDS")
            echo "prompt-cache-ttl"
            ;;
        "ROR_SUMMARY_PROMPT_ID")
            echo "ror-summary-prompt-id"
            ;;
        *)
            # Default: lowercase and replace underscores with hyphens
            echo "$env_name" | tr '[:upper:]' '[:lower:]' | tr '_' '-'
            ;;
    esac
}

# Function to create/update parameter
sync_parameter() {
    local env_name="$1"
    local env_value="$2"
    local param_name=$(env_to_param_name "$env_name")
    local param_path="/$ENVIRONMENT/bhulekha-extension/$param_name"

    # Skip if in skip list
    if should_skip_param "$env_name"; then
        echo "⏭️  Skipping $env_name (not needed in Parameter Store)"
        return
    fi

    # Skip if value is empty
    if [ -z "$env_value" ]; then
        echo "⚠️  Skipping $env_name (empty value)"
        return
    fi

    # Determine parameter type
    local param_type="String"
    if is_secure_param "$env_name"; then
        param_type="SecureString"
    fi

    # Check if parameter exists
    if aws ssm get-parameter --name "$param_path" --region "$AWS_REGION" &>/dev/null; then
        # Update existing parameter
        echo "📝 Updating $param_path (type: $param_type)"
        aws ssm put-parameter \
            --name "$param_path" \
            --value "$env_value" \
            --type "$param_type" \
            --overwrite \
            --region "$AWS_REGION" \
            --output json > /dev/null
        echo "   ✅ Updated"
    else
        # Create new parameter
        echo "➕ Creating $param_path (type: $param_type)"
        aws ssm put-parameter \
            --name "$param_path" \
            --value "$env_value" \
            --type "$param_type" \
            --description "Auto-synced from .env for $env_name" \
            --region "$AWS_REGION" \
            --output json > /dev/null
        echo "   ✅ Created"
    fi
}

# Read and process .env file
echo "Reading $ENV_FILE and syncing parameters..."
echo

# Counter for stats
TOTAL_COUNT=0
SYNCED_COUNT=0
SKIPPED_COUNT=0

while IFS='=' read -r key value; do
    # Skip comments and empty lines
    [[ "$key" =~ ^#.*$ ]] && continue
    [[ -z "$key" ]] && continue

    # Remove leading/trailing whitespace
    key=$(echo "$key" | xargs)
    value=$(echo "$value" | xargs)

    # Remove quotes from value if present
    value="${value%\"}"
    value="${value#\"}"
    value="${value%\'}"
    value="${value#\'}"

    TOTAL_COUNT=$((TOTAL_COUNT + 1))

    # Sync parameter
    if should_skip_param "$key"; then
        SKIPPED_COUNT=$((SKIPPED_COUNT + 1))
        echo "⏭️  Skipping $key (not needed in Parameter Store)"
    elif [ -z "$value" ]; then
        SKIPPED_COUNT=$((SKIPPED_COUNT + 1))
        echo "⚠️  Skipping $key (empty value)"
    else
        sync_parameter "$key" "$value"
        SYNCED_COUNT=$((SYNCED_COUNT + 1))
    fi
    echo

done < <(grep -v '^#' "$ENV_FILE" | grep -v '^$')

# Summary
echo "============================================================================"
echo "✅ SYNC COMPLETE"
echo "============================================================================"
echo "Total parameters in .env: $TOTAL_COUNT"
echo "Synced to Parameter Store: $SYNCED_COUNT"
echo "Skipped: $SKIPPED_COUNT"
echo
echo "Parameters are available at:"
echo "  /$ENVIRONMENT/bhulekha-extension/*"
echo
echo "To view all parameters:"
echo "  aws ssm describe-parameters \\"
echo "    --parameter-filters \"Key=Name,Option=BeginsWith,Values=/$ENVIRONMENT/bhulekha-extension\" \\"
echo "    --region $AWS_REGION"
echo
echo "To get a specific parameter:"
echo "  aws ssm get-parameter \\"
echo "    --name \"/$ENVIRONMENT/bhulekha-extension/anthropic-key\" \\"
echo "    --with-decryption \\"
echo "    --region $AWS_REGION"
echo
echo "Next steps:"
echo "  1. Run ./deploy-container.sh to deploy Lambda with Parameter Store access"
echo "  2. Lambda will automatically fetch secrets from Parameter Store"
echo "  3. Local development still uses .env file as fallback"
echo
echo "============================================================================"

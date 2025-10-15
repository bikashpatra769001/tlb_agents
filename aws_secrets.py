"""
AWS Parameter Store utility for retrieving secrets
Provides cached access to SSM Parameter Store with fallback to environment variables
"""
import os
from functools import lru_cache
from typing import Optional
import logging

logger = logging.getLogger(__name__)

# Flag to determine if we're running in AWS Lambda
IS_LAMBDA = os.getenv("AWS_EXECUTION_ENV") is not None

@lru_cache(maxsize=128)
def get_parameter(parameter_name: str, default: Optional[str] = None) -> Optional[str]:
    """
    Retrieve parameter from AWS Systems Manager Parameter Store with caching

    Args:
        parameter_name: The name/path of the parameter (e.g., '/prod/bhulekha/anthropic-key')
        default: Default value if parameter not found

    Returns:
        Parameter value as string, or default if not found

    Caching:
        Uses LRU cache to avoid repeated API calls within the same Lambda execution
        Cache persists for the lifetime of the Lambda container
    """
    # Try environment variable first (for local development)
    env_var = parameter_name.split('/')[-1].upper().replace('-', '_')
    env_value = os.getenv(env_var)

    if env_value:
        logger.info(f"✅ Using environment variable {env_var} for {parameter_name}")
        return env_value

    # If not in Lambda and no env var, return default
    if not IS_LAMBDA:
        logger.warning(f"⚠️  Not in Lambda and no env var for {parameter_name}, using default")
        return default

    # Fetch from Parameter Store (only in Lambda)
    try:
        import boto3
        from botocore.exceptions import ClientError

        # Use AWS_REGION from Lambda environment, fallback to ap-south-1
        region = os.getenv('AWS_REGION') or os.getenv('AWS_DEFAULT_REGION', 'ap-south-1')
        ssm = boto3.client('ssm', region_name=region)

        logger.info(f"🔍 Fetching parameter from SSM: {parameter_name}")
        response = ssm.get_parameter(
            Name=parameter_name,
            WithDecryption=True  # Decrypt SecureString parameters
        )

        value = response['Parameter']['Value']
        logger.info(f"✅ Successfully retrieved parameter: {parameter_name}")
        return value

    except ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code == 'ParameterNotFound':
            logger.warning(f"⚠️  Parameter not found: {parameter_name}, using default")
        else:
            logger.error(f"❌ AWS error retrieving parameter {parameter_name}: {e}")
        return default

    except Exception as e:
        logger.error(f"❌ Unexpected error retrieving parameter {parameter_name}: {e}")
        return default


def get_secrets() -> dict:
    """
    Retrieve all application secrets from Parameter Store

    Returns:
        Dictionary containing all secret values with fallbacks
    """
    # Define parameter paths (use hierarchical naming for organization)
    # Format: /environment/app-name/secret-name
    environment = os.getenv("ENVIRONMENT", "prod")

    secrets = {
        "anthropic_api_key": get_parameter(
            f"/{environment}/bhulekha-extension/anthropic-key",
            default=os.getenv("ANTHROPIC_API_KEY")  # Fallback to env var
        ),
        "supabase_url": get_parameter(
            f"/{environment}/bhulekha-extension/supabase-url",
            default=os.getenv("SUPABASE_URL")
        ),
        "supabase_key": get_parameter(
            f"/{environment}/bhulekha-extension/supabase-key",
            default=os.getenv("SUPABASE_KEY")
        ),
        "prompt_service_url": get_parameter(
            f"/{environment}/bhulekha-extension/prompt-service-url",
            default=os.getenv("PROMPT_SERVICE_URL", "https://5rp9zvhds7.ap-south-1.awsapprunner.com")
        ),
        "chrome_extension_id": get_parameter(
            f"/{environment}/bhulekha-extension/chrome-extension-id",
            default=os.getenv("CHROME_EXTENSION_ID", "")
        ),
    }

    logger.info(f"🔐 Loaded secrets for environment: {environment}")
    return secrets


def clear_cache():
    """Clear the parameter cache (useful for testing or forcing refresh)"""
    get_parameter.cache_clear()
    logger.info("🧹 Parameter cache cleared")

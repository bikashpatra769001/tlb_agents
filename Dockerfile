# Dockerfile for AWS Lambda Container Image
# This uses AWS Lambda Python 3.12 base image which includes the Lambda Runtime Interface Client

FROM public.ecr.aws/lambda/python:3.12

# Set working directory
WORKDIR ${LAMBDA_TASK_ROOT}

# Set DSPy cache directory to /tmp (Lambda writable directory)
ENV DSPY_CACHEDIR=/tmp/.dspy_cache

# Copy requirements file
COPY requirements.txt .

# Install Python dependencies
# Use pip instead of uv in container for better compatibility
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY api_server.py .
COPY prompt_service.py .
COPY aws_secrets.py .
COPY prompts/ ./prompts/

# Set the Lambda handler
# Format: filename.handler_function
CMD ["api_server.handler"]

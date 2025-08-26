# Claude Code Lambda Function

Introducing FAALF - <ins>F</ins>lexible <ins>A</ins>gent <ins>A</ins>s a <ins>L</ins>ambda <ins>F</ins>unction

This project provides a Docker container that runs Claude Code inside a Lambda function, allowing you to send flexible requests such as:

- write a script, execute it, then return the results
- search the web, summarize
- analyze my cloud infra and give recommendations for cost optimization or security improvements
- search my databases, query data, visualize, email the resulting graph
- recursive calls by a "parent" FAALF, spawning child tasks for task parallelization (be careful!)
- ...the possibilities are endless! 

Claude code is granted "--dangerously-skip-permissions" - meaning it has permissions for all actions within the lambda itself.  Guardrails for the lambda can be established using IAM permissions.  

This gives claude code full flexibility within its own ephemeral lambda sandbox space, but security is maintained through IAM least-privilege boundaries, trust relationships, and network configurations.

## Overview

The system consists of:
- **Dockerfile**: Creates a Lambda-compatible container with Claude Code installed
- **lambda_function.py**: Python handler that processes requests and runs Claude Code
- **docker-compose.yml**: Local testing environment
- **deploy.sh**: Deployment script for AWS Lambda
- **.env**: Environment configuration file

## Architecture

```
Client Request → Lambda Function → Secrets Manager → Claude Code → Python Execution → Response
```

1. Client invokes JSON payload with coding or research task
2. Lambda function retrieves Anthropic API key from AWS Secrets Manager
3. Lambda function creates temporary workspace
4. Claude Code processes the request using the API key
5. If `execute: true`, any created Python files are executed
6. Results are returned as JSON

## Prerequisites

- AWS CLI configured with appropriate permissions
- Docker and Docker Compose installed
- For local testing: AWS credentials configured in `~/.aws/` directory

## Setup

### Environment Configuration

1. **Create a `.env` file with your configuration:**
```bash
ANTHROPIC_API_KEY=your_anthropic_api_key_here
region=us-west-2
```

### AWS Deployment

1. **Deploy to AWS Lambda:**
```bash
./deploy.sh
```

This script will:
- Load configuration from `.env` file
- Create/update the Anthropic API key in AWS Secrets Manager
- Build and push Docker image to ECR
- Create or update the Lambda function
- Set up proper IAM permissions for Secrets Manager access

### Local Testing Setup

1. **Ensure AWS credentials are configured:**
```bash
# Your ~/.aws/ directory should contain:
# - credentials file with your AWS access keys
# - config file with default region
```

2. **Build and start the containers:**
```bash
docker-compose up -d
```

3. **Send a test request via curl:**
```bash
curl -X POST "http://localhost:9000/2015-03-31/functions/function/invocations" \
  -H "Content-Type: application/json" \
  -d '{
    "task": "write a script that prints hello world", 
    "execute": true
  }'
```

4. **Or use the test script:**
```bash
python test_local.py
```

## Testing Scripts

- **Local testing**: Use `test_local.py` for testing the Lambda function locally
- **Remote testing**: Use `test_lambda.py` for testing the deployed Lambda function on AWS

### Request Format

```json
{
  "task": "your coding or research request here",
  "execute": true  // optional, defaults to false
}
```

### Response Format

```json
{
  "statusCode": 200,
  "body": {
    "claude_output": "output from claude code",
    "claude_error": "any errors from claude code",
    "return_code": 0,
    "execution_results": [
      {
        "file": "script.py",
        "stdout": "hello world\n",
        "stderr": null,
        "return_code": 0
      }
    ]
  }
}
```

## Security

- **API Key Management**: The Anthropic API key is securely stored in AWS Secrets Manager
- **Local Testing**: AWS credentials are mounted read-only from your local `~/.aws/` directory
- **IAM Permissions**: Lambda function has minimal required permissions for Secrets Manager access

## Files

- `Dockerfile` - Container configuration with Python Lambda base + Node.js + Claude Code
- `lambda_function.py` - Lambda handler function with Secrets Manager integration
- `docker-compose.yml` - Local testing setup with AWS credentials mounting
- `requirements.txt` - Python dependencies including boto3
- `deploy.sh` - AWS deployment script
- `test_lambda.py` - Test script for Lambda function
- `.env` - Environment configuration (create this file)

## Local Development

```bash
# Stop containers
docker-compose down

# Rebuild after changes
docker-compose build

# Start again
docker-compose up -d

# View logs
docker-compose logs claude-lambda
```

## AWS Permissions Required

Your AWS user/role needs the following permissions:
- `ecr:*` - For Docker image management
- `lambda:*` - For Lambda function management
- `iam:CreateRole`, `iam:AttachRolePolicy`, `iam:PutRolePolicy` - For IAM role creation
- `secretsmanager:CreateSecret`, `secretsmanager:UpdateSecret`, `secretsmanager:GetSecretValue` - For API key management
- `sts:GetCallerIdentity` - For account ID lookup

## Troubleshooting

- **Local testing fails**: Ensure your `~/.aws/` directory contains valid credentials
- **Secrets Manager access denied**: Check IAM permissions and region settings
- **Docker build issues**: Ensure you have sufficient disk space and network access

## Future Work

- Effect of large libraries like numpy/pandas/sklearn - large images
- Check ability to do 'pip install xyz' within the same runtime
- Optimizing tokens/model.  Adding an option for model selection for cheaper models
- Selection of subscription vs API key
- Mapping IAM least-privelege permissions to specific FAALF prompt purposes
- "circuit breaker" for too many recursive invocations
- Cost threshold for api calls
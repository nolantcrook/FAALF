# Claude Code Lambda Function

Introducing FAALF (yeah I could do better) - **F**lexible **A**gent **A**s a **L**ambda **F**unction

This project provides a Docker container that runs Claude Code inside a Lambda function, allowing you to send flexible requests such as:

-write a script and execute it then return the results
-search the web, summarize, return results
-analyze my cloud infra and make changes (depending on permissions) or just give recommendations
-search my databases, query data, write a script to visualize, email me the resulting graph
-...the possibilities are endless!

Claude code is granted "--dangerously-skip-permissions" - meaning it has permissions for all actions.  However, guardrails for the lambda can be established using IAM permissions.  

This gives claude code full flexibility within its own ephemeral lambda sandbox space, but security is maintained through the IAM permission boundaries.

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

1. Client sends JSON payload with coding task
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

### Local Testing

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

3. **Send a test request:**
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
python test_lambda.py
```

### Request Format

```json
{
  "task": "your coding request here",
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
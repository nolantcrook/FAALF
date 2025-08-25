#!/bin/bash

set -e

# Load environment variables from .env file
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
fi

# Configuration
ECR_REPO_NAME="aalf"
LAMBDA_FUNCTION_NAME="aalf-function"
AWS_REGION=${region}
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
SECRET_NAME="anthropic-api-key-secret"

echo "Starting deployment for $ECR_REPO_NAME..."
echo "AWS Account ID: $AWS_ACCOUNT_ID"
echo "AWS Region: $AWS_REGION"

# Step 0: Create or update secrets manager with API key from .env
if [ -n "$ANTHROPIC_API_KEY" ]; then
    echo "Creating/updating secrets manager with API key..."
    
    # Try to update the secret first
    if aws secretsmanager update-secret \
        --secret-id $SECRET_NAME \
        --secret-string "$ANTHROPIC_API_KEY" \
        --region $AWS_REGION 2>/dev/null; then
        echo "API key updated in secrets manager"
    else
        # If update fails, create the secret
        echo "Secret doesn't exist, creating new secret..."
        aws secretsmanager create-secret \
            --name $SECRET_NAME \
            --description "Anthropic API Key for Claude Code Lambda" \
            --secret-string "$ANTHROPIC_API_KEY" \
            --region $AWS_REGION
        echo "API key created in secrets manager"
    fi
else
    echo "WARNING: ANTHROPIC_API_KEY not found in .env file"
fi

# Step 1: Create ECR repository if it doesn't exist
echo "Creating ECR repository..."
aws ecr describe-repositories --repository-names $ECR_REPO_NAME --region $AWS_REGION 2>/dev/null || \
    aws ecr create-repository --repository-name $ECR_REPO_NAME --region $AWS_REGION

# Get login token for ECR
echo "Logging into ECR..."
aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com

# Step 2: Build Docker image
echo "Building Docker image..."
docker buildx build --platform linux/amd64 --load -t $ECR_REPO_NAME .

# Step 3: Tag image for ECR
echo "Tagging Docker image..."
ECR_URI="$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPO_NAME:latest"
docker tag $ECR_REPO_NAME:latest $ECR_URI

# Step 4: Push image to ECR
echo "Pushing image to ECR..."
docker push $ECR_URI

# Step 5: Create or update Lambda function
echo "Creating/updating Lambda function..."

# Check if Lambda function exists
if aws lambda get-function --function-name $LAMBDA_FUNCTION_NAME --region $AWS_REGION 2>/dev/null; then
    echo "Lambda function exists. Updating..."
    aws lambda update-function-code \
        --function-name $LAMBDA_FUNCTION_NAME \
        --image-uri $ECR_URI \
        --region $AWS_REGION
else
    echo "Creating new Lambda function..."
    
    # Create execution role if it doesn't exist
    ROLE_NAME="aalf-lambda-role"
    ROLE_ARN=$(aws iam get-role --role-name $ROLE_NAME --query 'Role.Arn' --output text 2>/dev/null || echo "")
    
    if [ -z "$ROLE_ARN" ]; then
        echo "Creating Lambda execution role..."
        
        # Create trust policy
        cat > trust-policy.json << EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "lambda.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF
        
        aws iam create-role \
            --role-name $ROLE_NAME \
            --assume-role-policy-document file://trust-policy.json
        
        aws iam attach-role-policy \
            --role-name $ROLE_NAME \
            --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole
        
        # Create and attach policy for Secrets Manager access
        cat > secrets-policy.json << EOF
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "secretsmanager:GetSecretValue"
            ],
            "Resource": "arn:aws:secretsmanager:$AWS_REGION:$AWS_ACCOUNT_ID:secret:$SECRET_NAME*"
        }
    ]
}
EOF
        
        aws iam put-role-policy \
            --role-name $ROLE_NAME \
            --policy-name SecretsManagerAccess \
            --policy-document file://secrets-policy.json
        
        # Clean up temp files
        rm trust-policy.json secrets-policy.json
        
        # Wait a bit for role to propagate
        sleep 10
        
        ROLE_ARN=$(aws iam get-role --role-name $ROLE_NAME --query 'Role.Arn' --output text)
    else
        echo "Role exists, ensuring Secrets Manager permissions..."
        # Create and attach policy for Secrets Manager access for existing role
        cat > secrets-policy.json << EOF
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "secretsmanager:GetSecretValue"
            ],
            "Resource": "arn:aws:secretsmanager:$AWS_REGION:$AWS_ACCOUNT_ID:secret:$SECRET_NAME*"
        }
    ]
}
EOF
        
        aws iam put-role-policy \
            --role-name $ROLE_NAME \
            --policy-name SecretsManagerAccess \
            --policy-document file://secrets-policy.json
        
        rm secrets-policy.json
    fi
    
    aws lambda create-function \
        --function-name $LAMBDA_FUNCTION_NAME \
        --package-type Image \
        --code ImageUri=$ECR_URI \
        --role $ROLE_ARN \
        --region $AWS_REGION \
        --timeout 900 \
        --memory-size 2048
fi

echo "Deployment completed successfully!"
echo "ECR Repository: $ECR_URI"
echo "Lambda Function: $LAMBDA_FUNCTION_NAME"
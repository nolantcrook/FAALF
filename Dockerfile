# Based on working claude-docker setup adapted for AWS Lambda Python runtime
FROM --platform=linux/amd64 public.ecr.aws/lambda/python:3.12

# Install required system dependencies including Node.js for Claude CLI
RUN microdnf install -y \
    git \
    tar \
    gzip \
    sudo \
    shadow-utils \
    util-linux \
    && microdnf clean all

# Install Node.js 20 for Claude CLI
RUN curl -fsSL https://rpm.nodesource.com/setup_20.x | bash - \
    && microdnf install -y nodejs \
    && microdnf clean all

# Install Claude Code globally
RUN npm install -g @anthropic-ai/claude-code

# Create sbx_user1051 to match Lambda runtime user
RUN /usr/sbin/useradd -u 1051 -m -s /bin/bash sbx_user1051 && \
    mkdir -p /tmp/claude-home/.claude && \
    chown -R sbx_user1051:sbx_user1051 /tmp/claude-home

# Install Python dependencies for Lambda function
COPY requirements.txt ${LAMBDA_TASK_ROOT}/
RUN pip install -r requirements.txt

# Copy Lambda function handler
COPY lambda_function.py ${LAMBDA_TASK_ROOT}/


# Create directories for Claude configuration
RUN mkdir -p ${LAMBDA_TASK_ROOT}/.claude

# Set environment variables
ENV PATH="/var/lang/bin:/usr/local/bin:/usr/bin/:/bin:/opt/bin:${PATH}"
ENV PYTHONPATH="${LAMBDA_TASK_ROOT}:${PYTHONPATH}"
# Set the Lambda handler
CMD ["lambda_function.handler"]
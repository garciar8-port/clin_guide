#!/usr/bin/env bash
set -euo pipefail

# Usage: ./deploy.sh [image-tag] [environment]
#   image-tag    defaults to short git SHA
#   environment  defaults to "dev"

PROJECT="clinguide"
ENV="${2:-dev}"
REGION="${AWS_REGION:-us-east-1}"
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
REPO="${PROJECT}-${ENV}"
ECR_URI="${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/${REPO}"
TAG="${1:-$(git rev-parse --short HEAD)}"

echo "==> Deploying ${REPO}:${TAG} to ${ECR_URI}"
echo "    Region: ${REGION}  Account: ${ACCOUNT_ID}  Environment: ${ENV}"

# 1. ECR login
echo "==> Logging into ECR..."
aws ecr get-login-password --region "$REGION" | \
  docker login --username AWS --password-stdin \
  "${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com"

# 2. Build
echo "==> Building Docker image..."
docker build -t "${REPO}:${TAG}" .

# 3. Tag and push
echo "==> Pushing to ECR..."
docker tag "${REPO}:${TAG}" "${ECR_URI}:${TAG}"
docker tag "${REPO}:${TAG}" "${ECR_URI}:latest"
docker push "${ECR_URI}:${TAG}"
docker push "${ECR_URI}:latest"

# 4. Update ECS services
CLUSTER="${PROJECT}-${ENV}"
echo "==> Forcing new deployment on ${CLUSTER}..."
aws ecs update-service \
  --cluster "$CLUSTER" \
  --service "${CLUSTER}-api" \
  --force-new-deployment \
  --region "$REGION" \
  --no-cli-pager

aws ecs update-service \
  --cluster "$CLUSTER" \
  --service "${CLUSTER}-ui" \
  --force-new-deployment \
  --region "$REGION" \
  --no-cli-pager

# 5. Wait for stability
echo "==> Waiting for services to stabilize..."
aws ecs wait services-stable \
  --cluster "$CLUSTER" \
  --services "${CLUSTER}-api" "${CLUSTER}-ui" \
  --region "$REGION"

echo "==> Deploy complete!"
echo "    Image: ${ECR_URI}:${TAG}"

ALB_DNS=$(aws elbv2 describe-load-balancers \
  --names "${CLUSTER}-alb" \
  --region "$REGION" \
  --query "LoadBalancers[0].DNSName" \
  --output text 2>/dev/null || echo "unknown")
echo "    URL:   http://${ALB_DNS}"

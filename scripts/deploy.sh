#!/usr/bin/env bash
# =============================================================================
# POS System - AWS ECS Deployment Script
# =============================================================================
# Usage: ./scripts/deploy.sh <environment>
#   environment: staging | production
#
# Prerequisites:
#   - AWS CLI configured with appropriate credentials
#   - Docker logged in or able to log in to ECR
#   - jq installed
# =============================================================================

set -euo pipefail

# -- Colors -------------------------------------------------------------------
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

info()    { echo -e "${CYAN}[INFO]${NC} $1"; }
success() { echo -e "${GREEN}[OK]${NC}   $1"; }
warn()    { echo -e "${YELLOW}[WARN]${NC} $1"; }
error()   { echo -e "${RED}[ERR]${NC}  $1"; exit 1; }

# -- Configuration ------------------------------------------------------------
ENVIRONMENT="${1:-}"
if [ -z "$ENVIRONMENT" ]; then
    error "Usage: ./scripts/deploy.sh <staging|production>"
fi

if [ "$ENVIRONMENT" != "staging" ] && [ "$ENVIRONMENT" != "production" ]; then
    error "Invalid environment: $ENVIRONMENT. Must be 'staging' or 'production'."
fi

# AWS Configuration - override via environment variables or update defaults
AWS_REGION="${AWS_REGION:-me-south-1}"
AWS_ACCOUNT_ID="${AWS_ACCOUNT_ID:-$(aws sts get-caller-identity --query Account --output text)}"
ECR_REGISTRY="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"
ECS_CLUSTER="pos-${ENVIRONMENT}"
IMAGE_TAG="${IMAGE_TAG:-$(git rev-parse --short HEAD)}"
TIMESTAMP=$(date +%Y%m%d-%H%M%S)

# Service and repository names
BACKEND_REPO="pos-${ENVIRONMENT}/backend"
FRONTEND_REPO="pos-${ENVIRONMENT}/frontend"
BACKEND_SERVICE="pos-${ENVIRONMENT}-backend"
FRONTEND_SERVICE="pos-${ENVIRONMENT}-frontend"
MIGRATION_TASK="pos-${ENVIRONMENT}-migration"

echo ""
echo "========================================="
echo "  POS System - Deploy to ${ENVIRONMENT}"
echo "========================================="
echo ""
echo "  Cluster:    ${ECS_CLUSTER}"
echo "  Region:     ${AWS_REGION}"
echo "  Image Tag:  ${IMAGE_TAG}"
echo "  Timestamp:  ${TIMESTAMP}"
echo ""

# -- Safety check for production ----------------------------------------------
if [ "$ENVIRONMENT" = "production" ]; then
    warn "You are about to deploy to PRODUCTION."
    echo ""
    read -p "  Type 'yes-deploy-production' to confirm: " CONFIRM
    if [ "$CONFIRM" != "yes-deploy-production" ]; then
        error "Production deployment cancelled."
    fi
    echo ""
fi

# -- Step 1: Login to ECR ----------------------------------------------------
info "Logging in to ECR..."
aws ecr get-login-password --region "$AWS_REGION" | \
    docker login --username AWS --password-stdin "$ECR_REGISTRY"
success "ECR login successful"

# -- Step 2: Build Docker images ----------------------------------------------
info "Building backend image..."
docker build \
    -t "${ECR_REGISTRY}/${BACKEND_REPO}:${IMAGE_TAG}" \
    -t "${ECR_REGISTRY}/${BACKEND_REPO}:latest" \
    -f backend/Dockerfile \
    backend/
success "Backend image built"

info "Building frontend image..."
docker build \
    -t "${ECR_REGISTRY}/${FRONTEND_REPO}:${IMAGE_TAG}" \
    -t "${ECR_REGISTRY}/${FRONTEND_REPO}:latest" \
    -f frontend/Dockerfile \
    frontend/
success "Frontend image built"

# -- Step 3: Push images to ECR -----------------------------------------------
info "Pushing backend image..."
docker push "${ECR_REGISTRY}/${BACKEND_REPO}:${IMAGE_TAG}"
docker push "${ECR_REGISTRY}/${BACKEND_REPO}:latest"
success "Backend image pushed"

info "Pushing frontend image..."
docker push "${ECR_REGISTRY}/${FRONTEND_REPO}:${IMAGE_TAG}"
docker push "${ECR_REGISTRY}/${FRONTEND_REPO}:latest"
success "Frontend image pushed"

# -- Step 4: Run database migration -------------------------------------------
info "Running database migration task..."
MIGRATION_ARN=$(aws ecs run-task \
    --cluster "$ECS_CLUSTER" \
    --task-definition "$MIGRATION_TASK" \
    --launch-type FARGATE \
    --network-configuration "$(aws ecs describe-services \
        --cluster "$ECS_CLUSTER" \
        --services "$BACKEND_SERVICE" \
        --query 'services[0].networkConfiguration' \
        --output json)" \
    --overrides "{
        \"containerOverrides\": [{
            \"name\": \"migration\",
            \"command\": [\"alembic\", \"upgrade\", \"head\"],
            \"environment\": [{
                \"name\": \"IMAGE_TAG\",
                \"value\": \"${IMAGE_TAG}\"
            }]
        }]
    }" \
    --query 'tasks[0].taskArn' \
    --output text)

info "Waiting for migration task to complete..."
aws ecs wait tasks-stopped \
    --cluster "$ECS_CLUSTER" \
    --tasks "$MIGRATION_ARN"

# Check migration exit code
EXIT_CODE=$(aws ecs describe-tasks \
    --cluster "$ECS_CLUSTER" \
    --tasks "$MIGRATION_ARN" \
    --query 'tasks[0].containers[0].exitCode' \
    --output text)

if [ "$EXIT_CODE" != "0" ]; then
    error "Migration task failed with exit code: $EXIT_CODE. Aborting deployment."
fi
success "Database migration completed successfully"

# -- Step 5: Update ECS services -----------------------------------------------
info "Updating backend service..."
aws ecs update-service \
    --cluster "$ECS_CLUSTER" \
    --service "$BACKEND_SERVICE" \
    --force-new-deployment \
    --no-cli-pager > /dev/null
success "Backend service update initiated"

info "Updating frontend service..."
aws ecs update-service \
    --cluster "$ECS_CLUSTER" \
    --service "$FRONTEND_SERVICE" \
    --force-new-deployment \
    --no-cli-pager > /dev/null
success "Frontend service update initiated"

# -- Step 6: Wait for service stability ----------------------------------------
info "Waiting for services to stabilize (this may take several minutes)..."

aws ecs wait services-stable \
    --cluster "$ECS_CLUSTER" \
    --services "$BACKEND_SERVICE" "$FRONTEND_SERVICE"

success "All services are stable"

echo ""
echo "========================================="
echo "  Deployment Complete"
echo "========================================="
echo ""
echo "  Environment:  ${ENVIRONMENT}"
echo "  Image Tag:    ${IMAGE_TAG}"
echo "  Timestamp:    ${TIMESTAMP}"
echo ""

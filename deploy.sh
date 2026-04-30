#!/bin/bash
# Deploy to Google Cloud Run
# Usage: ./deploy.sh

# Configuration
PROJECT_ID="adp-413110"
SERVICE_NAME="drkhiri-rdv"
REGION="europe-west1"
IMAGE_NAME="gcr.io/${PROJECT_ID}/${SERVICE_NAME}"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  Deploying Dr. Khiri RDV to Cloud Run${NC}"
echo -e "${GREEN}========================================${NC}"

# Set project
echo -e "\n${YELLOW}1. Setting project...${NC}"
gcloud config set project ${PROJECT_ID}

# Enable required APIs
echo -e "\n${YELLOW}2. Enabling APIs...${NC}"
gcloud services enable cloudbuild.googleapis.com
gcloud services enable run.googleapis.com
gcloud services enable containerregistry.googleapis.com

# Build the image
echo -e "\n${YELLOW}3. Building Docker image...${NC}"
gcloud builds submit --tag ${IMAGE_NAME}

# Deploy to Cloud Run
echo -e "\n${YELLOW}4. Deploying to Cloud Run...${NC}"
gcloud run deploy ${SERVICE_NAME} \
    --image ${IMAGE_NAME} \
    --platform managed \
    --region ${REGION} \
    --allow-unauthenticated \
    --set-env-vars "GOOGLE_CLIENT_ID=${GOOGLE_CLIENT_ID}" \
    --set-env-vars "GOOGLE_CLIENT_SECRET=${GOOGLE_CLIENT_SECRET}" \
    --set-env-vars "GOOGLE_REFRESH_TOKEN=${GOOGLE_REFRESH_TOKEN}" \
    --set-env-vars "DOCTOR_EMAIL=${DOCTOR_EMAIL}" \
    --set-env-vars "GOOGLE_CALENDAR_ID=${GOOGLE_CALENDAR_ID}" \
    --set-env-vars "FRONTEND_URL=${FRONTEND_URL}" \
    --set-env-vars "API_SECRET_KEY=${API_SECRET_KEY}"

echo -e "\n${GREEN}========================================${NC}"
echo -e "${GREEN}  Deployment Complete!${NC}"
echo -e "${GREEN}========================================${NC}"

# Get the URL
gcloud run services describe ${SERVICE_NAME} --region ${REGION} --format 'value(status.url)'
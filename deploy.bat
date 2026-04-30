@echo off
REM Deploy to Google Cloud Run (Windows)
REM Usage: deploy.bat
REM
REM Set the following environment variables before running (or source from a local
REM untracked file like deploy.local.bat which is gitignored):
REM   GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REFRESH_TOKEN,
REM   DOCTOR_EMAIL, GOOGLE_CALENDAR_ID, API_SECRET_KEY
REM Also requires service-account.json in this directory (gitignored).

SET PROJECT_ID=adp-413110
SET SERVICE_NAME=drkhiri-rdv
SET REGION=europe-west1
SET IMAGE_NAME=gcr.io/%PROJECT_ID%/%SERVICE_NAME%

echo ========================================
echo   Deploying Dr. Khiri RDV to Cloud Run
echo ========================================

REM Authenticate with service account
echo.
echo 1. Authenticating with service account...
call gcloud auth activate-service-account --key-file=service-account.json

REM Set project
echo.
echo 2. Setting project...
call gcloud config set project %PROJECT_ID%

REM Enable required APIs
echo.
echo 3. Enabling APIs...
call gcloud services enable cloudbuild.googleapis.com
call gcloud services enable run.googleapis.com
call gcloud services enable containerregistry.googleapis.com

REM Build the image
echo.
echo 4. Building Docker image...
call gcloud builds submit --tag %IMAGE_NAME%

REM Deploy to Cloud Run with environment variables
echo.
echo 5. Deploying to Cloud Run...
call gcloud run deploy %SERVICE_NAME% ^
    --image %IMAGE_NAME% ^
    --platform managed ^
    --region %REGION% ^
    --allow-unauthenticated ^
    --memory 512Mi ^
    --cpu 1 ^
    --min-instances 0 ^
    --max-instances 10 ^
    --set-env-vars "GOOGLE_CLIENT_ID=%GOOGLE_CLIENT_ID%" ^
    --set-env-vars "GOOGLE_CLIENT_SECRET=%GOOGLE_CLIENT_SECRET%" ^
    --set-env-vars "GOOGLE_REFRESH_TOKEN=%GOOGLE_REFRESH_TOKEN%" ^
    --set-env-vars "DOCTOR_EMAIL=%DOCTOR_EMAIL%" ^
    --set-env-vars "GOOGLE_CALENDAR_ID=%GOOGLE_CALENDAR_ID%" ^
    --set-env-vars "API_SECRET_KEY=%API_SECRET_KEY%"

echo.
echo ========================================
echo   Deployment Complete!
echo ========================================
echo.

REM Get the URL
echo Service URL:
call gcloud run services describe %SERVICE_NAME% --region %REGION% --format "value(status.url)"

echo.
pause

```shell
REGION=asia-southeast1
PROJECT_ID=ethanhanjoonix-proj1
SERVICE=jit-cleanup
SERVICE_ACCOUNT_EMAIL=jitaccess@ethanhanjoonix-proj1.iam.gserviceaccount.com
REPO_NAME=jit-repo

docker build --platform linux/amd64 -t ${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO_NAME}/${SERVICE}:latest .
docker push ${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO_NAME}/${SERVICE}:latest
gcloud run deploy ${SERVICE} \
--image ${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO_NAME}/${SERVICE}:latest \
--service-account=${SERVICE_ACCOUNT_EMAIL} \
--region=${REGION} \
--port=8080 \
--memory=2G

# --set-env-vars=CAI_BUCKET_NAME=${_CAI_BUCKET_NAME} \
# --no-allow-unauthenticated \
```
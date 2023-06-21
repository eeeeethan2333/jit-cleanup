
```shell
REGION=asia-southeast1
PROJECT_ID=xxxxxxx
SERVICE=jit-cleanup
SERVICE_ACCOUNT_EMAIL=jitaccess@xxxxxxx.iam.gserviceaccount.com
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
SUBSCRIPTION_ID="jit-sub"
TOPIC_ID="jit-access"
gcloud pubsub subscriptions create $SUBSCRIPTION_ID --topic=$TOPIC_ID --project=$PROJECT_ID
```

```shell
REGION=asia-southeast1
PROJECT_ID=ethanhanjoonix-proj1
SERVICE=jit-cleanup
SERVICE_ACCOUNT_EMAIL=jitaccess@xxxxxxx.iam.gserviceaccount.com
REPO_NAME=jit-repo
PUBSUB_TOPIC_NAME=projects/ethanhanjoonix-proj1/topics/jit-access
PUBSUB_SUBSCRIPTION_PATH=projects/ethanhanjoonix-proj1/subscriptions/jit-sub

docker build --platform linux/amd64 -t ${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO_NAME}/${SERVICE}:latest .
docker push ${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO_NAME}/${SERVICE}:latest
gcloud run deploy ${SERVICE} \
--image ${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO_NAME}/${SERVICE}:latest \
--service-account=${SERVICE_ACCOUNT_EMAIL} \
--region=${REGION} \
--port=8080 \
--set-env-vars "PROJECT_ID=${PROJECT_ID}" \
--set-env-vars "PUBSUB_TOPIC_NAME=${PUBSUB_TOPIC_NAME}" \
--set-env-vars "PUBSUB_SUBSCRIPTION_PATH=${PUBSUB_SUBSCRIPTION_PATH}" \
--set-env-vars "NUM_MESSAGES=100" \
--memory=2G

# --set-env-vars=CAI_BUCKET_NAME=${_CAI_BUCKET_NAME} \
# --no-allow-unauthenticated \
SUBSCRIPTION_ID="jit-sub"
TOPIC_ID="jit-access"
gcloud pubsub subscriptions create $SUBSCRIPTION_ID --topic=$TOPIC_ID --project=$PROJECT_ID

gcloud scheduler jobs create http jit-cleanup --schedule "0 * * * *" --uri "https://jit-cleanup-y3xxuiynlq-as.a.run.app/scheduler" --http-method POST --message-body='{}'

```
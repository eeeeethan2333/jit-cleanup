# jit-cleanup

A Python web application which is cleans up expired [jit-access](https://github.com/GoogleCloudPlatform/jit-access) IAM permission bindings.


## Background
The [jit-access](https://github.com/GoogleCloudPlatform/jit-access) provides a mechanism to grant elevated IAM permission just in time. It does this by creating IAM user bindings with conditional access. These bindings can be replaced when expired, but they still exist in the project IAM policy after expiration. 

Whilst its permissible to have expired bindings in the IAM policy this has a few implications to consider
- Additional complexity when trying to review access permissions which include a lot of expired bindings
- IaC drift can occur when temporary permissions are implemented using direct API calls instead of IaC. This can lead to changes in the project IAM binding configuration, which can be an operational risk.
- Compliance issues caused by conditional bindings which violate PaC rules.

## Solution
Instead of storing state in a database, we use Pub/Sub to store events until they are processed or expire. This allows multiple components to act on published events from jit-acces, not just for removing conditional bindings. 

This solution demonstrates how to specifically clean up expired IAM bindings created by jit-access, based on messages send to a specific Pub/Sub topic.

The easiest way to handle expired user based bindings is to remove the conditional access after expiry. This can be accomplished by running a periodic cleanup task to remove expired bindings created by jit-access.

## Setup & Deployment
### Before You Start
Make sure you have the latest version of [JIT deployed in your GCP environment](https://cloud.google.com/architecture/manage-just-in-time-privileged-access-to-project)


### Setup Environment
Set the following environment variables, updating PROJECT_ID value:
```shell
PROJECT_ID=<SET VALUE HERE>
REGION=asia-southeast1
PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format 'value(projectNumber)')
SERVICE=jitcleanup
SERVICE_ACCOUNT_EMAIL=jitaccess@$PROJECT_ID.iam.gserviceaccount.com
PUBSUB_TOPIC_NAME=projects/$PROJECT_ID/topics/jit-access
SUBSCRIPTION_ID=jit-binding
PUBSUB_SUBSCRIPTION_PATH=projects/$PROJECT_ID/subscriptions/$SUBSCRIPTION_ID
```

Create a specific pubsub subscription that only recieves jit-binding messages. The ack-deadline determines how long a message takes to re-appear on the queue.
```
gcloud pubsub subscriptions create $SUBSCRIPTION_ID --topic=$PUBSUB_TOPIC_NAME \
--project=$PROJECT_ID \
--ack-deadline=300 \
--message-filter="(attributes.origin=\"jit-binding\")"
```
### Build Deployment
Build the container image and push it to your container registry.
```
docker build --platform linux/amd64 -t gcr.io/${PROJECT_ID}/${SERVICE}:latest .
docker push gcr.io/${PROJECT_ID}/${SERVICE}:latest
```
create an app.yaml file to configure and deploy the container
```
cat << EOF > app.yaml

apiVersion: serving.knative.dev/v1
kind: Service
metadata:
  name: ${SERVICE}
  namespace: ${PROJECT_NUMBER}
  labels:
    cloud.googleapis.com/location: $REGION
  annotations:
    run.googleapis.com/ingress: internal
spec:
  template:
    spec:
      serviceAccountName: $SERVICE_ACCOUNT_EMAIL
      containers:
      - image: gcr.io/${PROJECT_ID}/${SERVICE}:latest
        env:
        - name: PROJECT_ID
          value: "${PROJECT_ID}"
        - name: NUM_MESSAGES
          value: "20"
        - name: PUBSUB_TOPIC_NAME
          value: "${PUBSUB_TOPIC_NAME}"
        - name: PUBSUB_SUBSCRIPTION_PATH
          value: "${PUBSUB_SUBSCRIPTION_PATH}"
EOF
```
### Deploy
Deploy the container
```
gcloud run services replace app.yaml
RUN_SERVICE=$(gcloud run services describe ${SERVICE} --format 'value(status.address.url)')
```
Add IAM permissions to allow the service account to invoke Cloud Run service:
```
gcloud run services add-iam-policy-binding ${SERVICE} \
   --member=serviceAccount:${SERVICE_ACCOUNT_EMAIL} \
   --role=roles/run.invoker
```
Create a regular cleanup job to run on the hour, every hour:
```
gcloud scheduler jobs create http ${SERVICE} --schedule "0 * * * *" --uri "$RUN_SERVICE/scheduler" \
--oidc-service-account-email=${SERVICE_ACCOUNT_EMAIL} \
--location=$REGION \
--http-method POST --headers Content-Type=application/json \
--message-body='{}'
```


### Local Development Setup
Set the following environment variable when running locally for development
```bash
export PROJECT_ID=<SET VALUE HERE>
export PUBSUB_TOPIC_NAME=projects/$PROJECT_ID/topics/jit-access
export SUBSCRIPTION_ID=jit-binding
export PUBSUB_SUBSCRIPTION_PATH=projects/$PROJECT_ID/subscriptions/$SUBSCRIPTION_ID
python main.py
```
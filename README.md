# jit-cleanup

This is python web application which is to clean up [jit-access](https://github.com/GoogleCloudPlatform/jit-access) expired permission.


## Background
There is an existing solution published on the GCP architecture site which provides just in time access, open sourced as [jit-access](https://github.com/GoogleCloudPlatform/jit-access). It leverages an IAP protected application and templated IAM permissions to grant users time based privileged access. It provides a robust solution that includes logging, self approval, multi-party approval and variable time based access.
Under the hood it creates specific user permissions with IAM conditions to enforce time based access. The tool is additive, and each new request generates a user IAM binding with a new condition, unless the variable PURGE_EXISTING_TEMPORARY_BINDINGS  (currently undocumented)  is set in the app.yaml. In that scenario only a single conditional access binding per user is maintained.

Here is [how to setup](https://cloud.google.com/architecture/manage-just-in-time-privileged-access-to-project) JIT in GCP.

In general purging temporary bindings option will avoid hitting limits on max conditional bindings, but there are some challenges to implement this sometimes, including:

- IaC drift: will occur when temporary permissions are implemented using direct API calls instead of IaC. This can lead to changes in the project IAM binding configuration, which can be an operational risk.
- Compliance issue: Any JIT conditional bindings may trigger a failure in PaC unless we can exclude them.

## Solution
The easiest way to handle expired user based bindings is to remove the conditional access after expiry. This can be accomplished by running a periodic cleanup task to remove expired bindings.
Instead of storing state in a database, we can use PubSub to store events until they are processed. This allows multiple components to act on published events, not just for removing conditional bindings. This provides more flexibility and scalability.



## Deployment setup
### Before You Start
Make sure you have the latest version of [JIT deployed in your GCP environment](https://cloud.google.com/architecture/manage-just-in-time-privileged-access-to-project)


### Deploy code
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


### Local Development
Set the following environment variable when running locally for development
```bash
export NUM_MESSAGES=20
export PROJECT_ID=xxx
export PUBSUB_SUBSCRIPTION_PATH=projects/xxx/subscriptions/jit-sub
export PUBSUB_TOPIC_NAME=projects/xxx/topics/jit-access
python main.py
```
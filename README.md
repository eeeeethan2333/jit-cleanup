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
Make sure you have the [JIT developed in your GCP environment](https://cloud.google.com/architecture/manage-just-in-time-privileged-access-to-project)


### Deploy code
```shell
REGION=asia-southeast1
PROJECT_ID=xxx
SERVICE=jit-cleanup
SERVICE_ACCOUNT_EMAIL=jitaccess@xxx.iam.gserviceaccount.com
REPO_NAME=jit-repo
PUBSUB_TOPIC_NAME=projects/xxx/topics/jit-access
PUBSUB_SUBSCRIPTION_PATH=projects/xxx/subscriptions/jit-sub

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
--memory=2G \
--no-allow-unauthenticated

# --set-env-vars=CAI_BUCKET_NAME=${_CAI_BUCKET_NAME} \

SUBSCRIPTION_ID="jit-sub"
TOPIC_ID="jit-access"

# NOTE: the subscription haves to be created together with the topic.
# Please refer to Jit with pubsub integration guide
gcloud pubsub subscriptions create $SUBSCRIPTION_ID --topic=$TOPIC_ID \
--project=$PROJECT_ID \
--ack-deadline=300 \
--message-filter="(attributes.origin=\"jit-binding\")"

gcloud scheduler jobs create http jit-cleanup --schedule "0 * * * *" --uri "https://jit-cleanup-y3xxuiynlq-as.a.run.app/scheduler" \
--oidc-service-account-email=${SERVICE_ACCOUNT_EMAIL} \
--http-method POST --headers Content-Type=application/json \
--message-body='{}' \
--timeout=500

```


### Local Development

```bash
export NUM_MESSAGES=100
export PROJECT_ID=xxx
export PUBSUB_SUBSCRIPTION_PATH=projects/xxx/subscriptions/jit-sub
export PUBSUB_TOPIC_NAME=projects/xxx/topics/jit-access
python main.py
```
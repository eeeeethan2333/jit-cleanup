import json
import logging
import subprocess
from datetime import datetime

import google.auth
import googleapiclient.discovery
from google.api_core import retry
from google.cloud import pubsub_v1
from google.oauth2 import service_account  # type: ignore

logging.basicConfig()


# jit_cleaner fetches message from pubsub with max=NUM_MESSAGES
# only process the origin is jit-approval which is stored in pubsub message attribute
# based on condition start and expire, decide whether need to clean up
# or republish.
# https://cloud.google.com/iam/docs/granting-changing-revoking-access#single-role
# https://cloud.google.com/resource-manager/reference/rest/v1/projects/getIamPolicy
# https://cloud.google.com/run/docs/tutorials/gcloud
def jit_cleaner():
    # TODO(developer)
    project_id = "ethanhanjoonix-proj1"
    NUM_MESSAGES = 3
    # subscription_id = "your-subscription-id"
    # Number of seconds the subscriber should listen for messages
    # timeout = 5.0
    print("cleanup process")
    subscriber = pubsub_v1.SubscriberClient()
    # The `subscription_path` method creates a fully qualified identifier
    # in the form `projects/{project_id}/subscriptions/{subscription_id}`
    subscription_path = subscriber.subscription_path(project_id, "jit-sub")

    # credentials = service_account.Credentials.from_service_account_file(
    #   filename=os.environ["GOOGLE_APPLICATION_CREDENTIALS"],
    #   scopes=["https://www.googleapis.com/auth/cloud-platform"],
    # )
    credentials, _ = google.auth.default()
    service = googleapiclient.discovery.build(
      "cloudresourcemanager", "v1", credentials=credentials
    )
    policy = (
      service.projects()
      .getIamPolicy(
        resource=project_id,
        body={"options": {"requestedPolicyVersion": 3}},
      )
      .execute()
    )
    print(policy)

    # Wrap subscriber in a 'with' block to automatically call close() when done.
    with subscriber:
        # The subscriber pulls a specific number of messages. The actual
        # number of messages pulled may be smaller than max_messages.
        response = subscriber.pull(
          request={"subscription": subscription_path,
                   "max_messages": NUM_MESSAGES},
          retry=retry.Retry(deadline=300),
        )

        if len(response.received_messages) == 0:
            print(
              f"Received 0 message."
            )
            return

        ack_ids = []
        for received_message in response.received_messages:
            # in the design doc,
            # filter based on origin.
            # process based on expire. if false ignore.
            #

            print(f"Received: {received_message.message.data}.")

            print(f"attributes: {received_message.message.attributes}")
            user = received_message.message.attributes.get("user", "")
            origin = received_message.message.attributes.get("origin", "")
            condition = received_message.message.attributes.get("condition", "")

            condition_dict = json.loads(condition)
            start = condition_dict.get("start", "1900-01-01T00:00:00.00000Z")
            # start_datetime = datetime.fromisoformat(start)
            start_datetime = datetime.strptime(start, "%Y-%m-%dT%H:%M:%S.%fZ")
            end = condition_dict.get("end", "1900-01-01T00:00:00.00000Z")
            # end_datetime = datetime.fromisoformat(end)
            end_datetime = datetime.strptime(end, "%Y-%m-%dT%H:%M:%S.%fZ")
            print(
              f"{user}, {origin}, {condition_dict}, {start_datetime}, {end_datetime}")
            ack_ids.append(received_message.ack_id)

            # filter by date.
            # 1,2,3,4
            #
            if end_datetime < datetime.utcnow():
                target_project_id = project_id
                member_email = 'dev1@ethanhan.joonix.net'
                role = 'roles/browser'
                # same with gcloud
                # condition = '^|^expression=(request.time >= timestamp("2023-07-03T04:48:59.603364Z") && request.time < timestamp("2023-07-03T04:53:59.603364Z"))|title=JIT access activation|description=Self-approved, justification: 1248'

                condition = '^|^expression=(request.time >= timestamp("2023-07-03T08:07:02.98461Z") && request.time < timestamp("2023-07-03T08:12:02.98461Z"))|title=JIT access activation|description=Self-approved, justification: 1606'
                # https://cloud.google.com/sdk/gcloud/reference/projects/remove-iam-policy-binding
                # exmaple:
                # gcloud projects remove-iam-policy-binding ethanhanjoonix-proj1
                #   --member='user:dev1@ethanhan.joonix.net' --role='roles/browser' \
                #   --condition='^|^expression=(request.time >= timestamp("2023-07-03T04:22:42.35312Z") && request.time < timestamp("2023-07-03T04:27:42.35312Z"))|title=JIT access activation|description=Self-approved, justification: 1222'
                #   --verbosity=debug
                print(f"access expired: {received_message.message}")

                result = subprocess.run(
                  [
                    "gcloud", "projects", "remove-iam-policy-binding",
                    target_project_id,
                    f"--member=user:{member_email}".format(
                      member_email=member_email),
                    f"--role={role}".format(role=role),
                    # "--condition='expression=request.time < timestamp("2019-01-01T00:00:00Z"),title=expires_end_of_2018,description=Expires at midnight on 2018-12-31'
                    f"--condition={condition}".format(condition=condition),
                    "--verbosity=debug"
                  ],
                  capture_output=True,
                  text=True,
                  # shell=True
                )
                print(result.stdout)
                print(result.stderr)
                print(result.returncode)



            else:
                publisher = pubsub_v1.PublisherClient()
                topic_path = publisher.topic_path(project_id, "jit-access")
                future = publisher.publish(
                  topic_path,
                  received_message.message.data,
                  origin=origin,
                  user=user,
                  condition=condition
                )
                print("putting back to queue", future.result())

        # Acknowledges the received messages so they will not be sent again.
        subscriber.acknowledge(
          request={"subscription": subscription_path, "ack_ids": ack_ids}
        )

        print(
          f"Received and acknowledged {len(response.received_messages)} messages from {subscription_path}."
        )

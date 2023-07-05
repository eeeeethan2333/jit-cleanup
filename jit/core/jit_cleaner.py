import json
from datetime import datetime

import google.auth
import googleapiclient.discovery
from google.api_core import retry
from google.cloud import pubsub_v1
from google.oauth2 import service_account  # type: ignore

from jit.utils import config
from jit.utils import constant


def modify_policy_remove_member(conf: config.JitConfig, target_project: str,
  role: str, member: str,
  start: datetime, end: datetime) -> dict:
    """Removes a  member from a role binding."""
    credentials, _ = google.auth.default()
    service = googleapiclient.discovery.build(
      "cloudresourcemanager", "v1", credentials=credentials
    )
    policy = (
      service.projects()
      .getIamPolicy(
        # TODO: target project
        resource=conf.project_id,
        body={"options": {"requestedPolicyVersion": 3}},
      )
      .execute()
    )
    print(policy)
    # binding = next(b for b in policy["bindings"] if b["role"] == role)
    # if "members" in binding and member in binding["members"]:
    #     binding["members"].remove(member)
    # print(binding)
    policy = (
      service.projects()
      .setIamPolicy(resource=target_project, body={"policy": policy})
      .execute()
    )

    return policy


def process_pubsub_msg(conf, received_message):
    print(f"Received: {received_message.message.data}.")

    print(f"attributes: {received_message.message.attributes}")
    origin = received_message.message.attributes.get("origin", "")
    # for invalid origin, we should directly return and make the run_jit_cleaner
    # ack the message.
    if not origin or constant.MessageOrigin.from_str(
      origin) != constant.MessageOrigin.APPROVAL:
        print(
          f"origin invalid: origin={origin}, msg data = {received_message.message.data}.")
        return

        # if any of these process invalid, it may raise exception,
    # the exception will be captured in run_jit_cleaner level
    pubsub_msg_dict = json.loads(received_message.message.data)
    target_project_id = pubsub_msg_dict["project_id"]
    condition = pubsub_msg_dict["condition"]
    expression = condition["expression"]
    member = pubsub_msg_dict["user"]
    role = pubsub_msg_dict["role"]

    start = expression.get("start", "1900-01-01T00:00:00.00000Z")
    # start_datetime = datetime.fromisoformat(start)
    start_datetime = datetime.strptime(start, "%Y-%m-%dT%H:%M:%S.%fZ")
    end = expression.get("end", "1900-01-01T00:00:00.00000Z")
    # end_datetime = datetime.fromisoformat(end)
    end_datetime = datetime.strptime(end, "%Y-%m-%dT%H:%M:%S.%fZ")
    print(
      f"{member}, {origin}, {condition}, {start_datetime}, {end_datetime}")

    # filter by date.
    # 1,2,3,4
    #
    if end_datetime < datetime.utcnow():
        print(f"access expired: {received_message.message}")
        modify_policy_remove_member(conf, target_project_id, role, member,
                                    start, end)
    else:
        publisher = pubsub_v1.PublisherClient()
        future = publisher.publish(
          conf.topic_path,
          received_message.message.data,
          origin=origin
        )
        print("putting back to queue", future.result())


def run_jit_cleaner(conf: config.JitConfig):
    """
    jit_cleaner fetches message from pubsub with max=NUM_MESSAGES
    only process the origin is jit-approval which is stored in pubsub message attribute
    based on condition start and expire, decide whether need to clean up
    or republish.
    https://cloud.google.com/iam/docs/granting-changing-revoking-access#single-role
    https://cloud.google.com/resource-manager/reference/rest/v1/projects/getIamPolicy
    https://cloud.google.com/run/docs/tutorials/gcloud
    :return:
    """

    print("cleanup process")
    subscriber = pubsub_v1.SubscriberClient()

    # Wrap subscriber in a 'with' block to automatically call close() when done.
    with subscriber:
        # The subscriber pulls a specific number of messages. The actual
        # number of messages pulled may be smaller than max_messages.
        response = subscriber.pull(
          request={"subscription": conf.pubsub_subscription_path,
                   "max_messages": conf.num_messages},
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
            try:
                process_pubsub_msg(conf, received_message)
            except Exception as e:
                print("process pubsub exception: ", e)
                continue
            ack_ids.append(received_message.ack_id)
        # Acknowledges the received messages so they will not be sent again.
        subscriber.acknowledge(
          request={"subscription": conf.pubsub_subscription_path,
                   "ack_ids": ack_ids}
        )
        print(
          f"Received and acknowledged {len(response.received_messages)} messages from {conf.pubsub_subscription_path}."
        )

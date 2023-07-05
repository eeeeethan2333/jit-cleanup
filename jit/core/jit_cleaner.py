import json
from datetime import datetime

import google.auth
import googleapiclient.discovery
from google.api_core import retry
from google.cloud import pubsub_v1
from google.oauth2 import service_account  # type: ignore

from jit.utils import config
from jit.utils import constant
from jit.utils.logger import jit_logger


def modify_policy_remove_member(conf: config.JitConfig, target_project: str,
  role: str, member: str,
  start: datetime, end: datetime):
    """Removes a  member from a role binding."""
    jit_logger.info(
      "modify_policy_remove_member. config=%s, target_project=%s, role=%s, member=%s, start=%s, end=%s",
      conf, target_project, role, member, start, end
    )
    credentials, _ = google.auth.default()
    service = googleapiclient.discovery.build(
      "cloudresourcemanager", "v1", credentials=credentials
    )
    policy = (
      service.projects()
      .getIamPolicy(
        resource=target_project,
        body={"options": {"requestedPolicyVersion": 3}},
      )
      .execute()
    )
    jit_logger.debug(
      "retrived policy. policy=%s, project=%s", policy, target_project
    )
    expression = f"(request.time >= timestamp(\"{start}\") && request.time < timestamp(\"{end}\"))"
    if len(policy.get("bindings", [])) == 0:
        jit_logger.error("project binding empty. ")
        return
    binding_count = 0
    for b in policy["bindings"]:
        if (
          role == b["role"] and
          member in b["members"] and
          expression == b.get("condition", {}).get("expression", "")
        ):
            b["members"].remove(member)
            binding_count += 1
            continue

    policy["bindings"][:] = [b for b in policy["bindings"] if b["members"]]
    # if "members" in binding and member in binding["members"]:
    #     binding["members"].remove(member)
    # jit_logger.info(binding)

    service.projects().setIamPolicy(
      resource=target_project,
      body={"policy": policy}
    ).execute()
    jit_logger.info("%d binding has been removed.", binding_count)


def process_pubsub_msg(conf, received_message):
    jit_logger.info(f"Received: {received_message.message.data}.")
    jit_logger.info(f"attributes: {received_message.message.attributes}")
    origin = received_message.message.attributes.get("origin", "")
    # for invalid origin, we should directly return and make the run_jit_cleaner
    # ack the message.
    if not origin or constant.MessageOrigin.from_str(
      origin) != constant.MessageOrigin.BINDING:
        jit_logger.error(
          f"origin invalid: origin={origin}, msg data = {received_message.message.data}.")
        return

        # if any of these process invalid, it may raise exception,
    # the exception will be captured in run_jit_cleaner level
    pubsub_msg_dict = json.loads(received_message.message.data)
    target_project_id = pubsub_msg_dict["project_id"]
    condition = pubsub_msg_dict["conditions"]
    expression = condition["expression"]
    member = "user:{user}".format(user=pubsub_msg_dict["user"])
    role = pubsub_msg_dict["role"]

    start = expression.get("start", "1900-01-01T00:00:00.00000Z")
    # start_datetime = datetime.fromisoformat(start)
    start_datetime = datetime.strptime(start, "%Y-%m-%dT%H:%M:%S.%fZ")
    end = expression.get("end", "1900-01-01T00:00:00.00000Z")
    # end_datetime = datetime.fromisoformat(end)
    end_datetime = datetime.strptime(end, "%Y-%m-%dT%H:%M:%S.%fZ")

    # filter by date.
    # 1,2,3,4
    #
    if end_datetime < datetime.utcnow():
        jit_logger.info(f"access expired: {received_message.message}")
        modify_policy_remove_member(conf, target_project_id, role, member,
                                    start, end)
    else:
        publisher = pubsub_v1.PublisherClient()
        future = publisher.publish(
          conf.pubsub_topic_name,
          received_message.message.data,
          origin=origin
        )
        jit_logger.info("putting back to queue. msg_id=%s", future.result())


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

    jit_logger.info("cleanup process")
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
            jit_logger.info(
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
                jit_logger.info("process pubsub exception: ", e)
                continue
            ack_ids.append(received_message.ack_id)
        # Acknowledges the received messages so they will not be sent again.
        subscriber.acknowledge(
          request={"subscription": conf.pubsub_subscription_path,
                   "ack_ids": ack_ids}
        )
        jit_logger.info(
          f"Received and acknowledged {len(response.received_messages)} messages from {conf.pubsub_subscription_path}."
        )

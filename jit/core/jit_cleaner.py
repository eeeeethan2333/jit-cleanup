import json
from datetime import datetime
from datetime import timedelta
from datetime import timezone
from typing import MutableSequence

import google.auth
import googleapiclient.discovery
from google.api_core import retry
from google.cloud import pubsub_v1
from google.oauth2 import service_account  # type: ignore

from jit.utils import config
from jit.utils import constant
from jit.utils import string_utils
from jit.utils.logger import jit_logger


def republish(pubsub_topic_name, message_data, jit_origin):
    publisher = pubsub_v1.PublisherClient()
    future = publisher.publish(
      pubsub_topic_name,
      message_data,
      origin=jit_origin
    )
    jit_logger.info(
      "putting back to queue. jit_origin=%s, message_data=%s, msg_id=%s",
      jit_origin, message_data, future.result()
    )


def modify_policy_remove_member(conf: config.JitConfig, target_project: str,
  role: str, member: str,
  start: datetime, end: datetime):
    """
    Removes a member from a role binding.
    If removed return true, if not existing return false
    :param conf:
    :param target_project:
    :param role:
    :param member:
    :param start:
    :param end:
    :return: is_success, error_message

    :raises:
        ~google.auth.exceptions.DefaultCredentialsError:
            If no credentials were found, or if the credentials found were
            invalid.
        ~google.auth.exceptions.MutualTLSChannelError:
            if there are any problems
            setting up mutual TLS channel.
    """
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
      "retrieved policy. policy=%s, project=%s", policy, target_project
    )
    expression = f"(request.time >= timestamp(\"{start}\") && request.time < timestamp(\"{end}\"))"
    if len(policy.get("bindings", [])) == 0:
        jit_logger.warn(
          "project binding empty. config=%s, target_project=%s, role=%s, member=%s, start=%s, end=%s",
          conf, target_project, role, member, start, end
        )
        return
    binding_count = 0
    for b in policy["bindings"]:
        # In order to delete a binding we need to match the original binding request, including
        # the member, role, expression and condition title. This is to prevent deleting any other
        # conditional bindings that were not created by JIT.
        if (
          role == b["role"] and
          member in b["members"] and
          expression == b.get("condition", {}).get("expression", "") and
          constant.ACTIVATION_CONDITION_TITLE == b.get("condition", {}).get(
          "title", "")
        ):
            b["members"].remove(member)
            binding_count += 1
            continue
    if not binding_count:
        jit_logger.warn(
          "policy binding not found. config=%s, target_project=%s, role=%s, member=%s, start=%s, end=%s",
          conf, target_project, role, member, start, end
        )
        return
    policy["bindings"][:] = [b for b in policy["bindings"] if b["members"]]

    # Update the project IAM policy
    service.projects().setIamPolicy(
      resource=target_project,
      body={"policy": policy}
    ).execute()
    jit_logger.info("%d binding has been removed.", binding_count)
    return


def process_pubsub_msg(conf: config.JitConfig,
  received_message: MutableSequence["ReceivedMessage"]) -> bool:
    """
    if message expired, call modify_policy_remove_member to remove the binding.

    if current datetime > publishTime + 6 days
    then republish the message, and ack original msg

    if not expire, don't acknowledge,
    as we dont expect it to appear in the queue before ack timeout.
    :param conf:
    :param received_message:
    :return: is_ack bool
    """

    jit_logger.info(f"Received: {received_message.message.data}.")
    jit_logger.info(f"attributes: {received_message.message.attributes}")
    origin = received_message.message.attributes.get("origin", "")
    # for invalid origin, we should directly return and make the run_jit_cleaner
    # ack the message. However this typically means that the pubsub subscription filter is wrong
    if not origin or constant.MessageOrigin.from_str(
      origin) != constant.MessageOrigin.BINDING:
        jit_logger.error(
          f"origin invalid: origin={origin}, msg data = {received_message.message.data}. Check your pubsub subscription filter")
        return True

    # if any of these process invalid, it may raise exception,
    # the exception will be captured in run_jit_cleaner level
    pubsub_msg_dict = json.loads(received_message.message.data)
    payload = pubsub_msg_dict["payload"]
    target_project_id = payload["project_id"]
    condition = payload["conditions"]
    expression = condition["expression"]
    member = "user:{user}".format(user=payload["user"])
    role = payload["role"]

    start = expression.get("start", "1900-01-01T00:00:00.00000Z")
    end = expression.get("end", "1900-01-01T00:00:00.00000Z")
    
    end_datetime = string_utils.try_parsing_date(
      end, ["%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ"]
    )

    publish_time = received_message.message.publish_time.astimezone(
      timezone.utc)
    time_for_now = datetime.now(timezone.utc)
    if end_datetime < time_for_now:
        jit_logger.info(
          f"access expired: {received_message.message}, cleanup required.")
        modify_policy_remove_member(conf, target_project_id, role, member,
                                    start, end)
    elif publish_time + timedelta(days=6) < time_for_now:
        republish(conf.pubsub_topic_name, received_message.message.data,
                  constant.MessageOrigin.BINDING.value)
    else:
        # rest of the cases are not expired cases, we dont do ack and the message will reappear on the queue
        return False
    # if we've dealt with the message then we will ACK it
    return True


def run_jit_cleaner(conf: config.JitConfig):
    """
    jit_cleaner fetches message from pubsub with max=NUM_MESSAGES by loop
    until it consume all the message in pubsub
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

        while True:
            # The subscriber pulls a specific number of messages. The actual
            # number of messages pulled may be smaller than max_messages.
            response = subscriber.pull(
              request={"subscription": conf.pubsub_subscription_path,
                       "max_messages": conf.num_messages},
              retry=retry.Retry(deadline=300),
            )

            if len(response.received_messages) == 0:
                jit_logger.info(
                  f"Received 0 message. PubSub subscription({conf.pubsub_subscription_path}) is empty."
                )
                break

            ack_ids = []
            for received_message in response.received_messages:
                is_ack = True
                try:
                    is_ack = process_pubsub_msg(conf, received_message)

                except (google.auth.exceptions.MutualTLSChannelError,
                        google.auth.exceptions.DefaultCredentialsError) as google_ex:
                    # if google api exception,
                    # we should not ack it, and make it reappear.
                    jit_logger.exception(
                      "process pubsub google api exception: %s",
                      google_ex)
                    republish(conf.pubsub_topic_name,
                              received_message.message.data,
                              constant.MessageOrigin.ERROR.value)
                    is_ack = True

                except Exception as e:
                    # if general exception, basically data format issues.
                    # we directly ignore the message and ack it.
                    jit_logger.exception("process pubsub exception: %s", e)
                    republish(conf.pubsub_topic_name,
                              received_message.message.data,
                              constant.MessageOrigin.ERROR.value)
                    is_ack = True
                ack_ids += [received_message.ack_id] if is_ack else []

            if not ack_ids:
                continue

            # Acknowledges the received messages so they will not be sent again.
            subscriber.acknowledge(
              request={"subscription": conf.pubsub_subscription_path,
                       "ack_ids": ack_ids}
            )
            jit_logger.info(
              f"Received and acknowledged {len(response.received_messages)} messages from {conf.pubsub_subscription_path}."
            )

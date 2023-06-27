from datetime import datetime
import json
import logging

from google.cloud import pubsub_v1
from google.api_core import retry

logging.basicConfig()

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

    # Wrap subscriber in a 'with' block to automatically call close() when done.
    with subscriber:
        # The subscriber pulls a specific number of messages. The actual
        # number of messages pulled may be smaller than max_messages.
        response = subscriber.pull(
            request={"subscription": subscription_path, "max_messages": NUM_MESSAGES},
            retry=retry.Retry(deadline=300),
        )

        if len(response.received_messages) == 0:
            print(
                f"Received 0 message."
            )
            return

        ack_ids = []
        for received_message in response.received_messages:
            print(f"Received: {received_message.message.data}.")

            print(f"attributes: {received_message.message.attributes}")
            user = received_message.message.attributes.get("user", "")
            origin = received_message.message.attributes.get("origin", "")
            condition = received_message.message.attributes.get("condition", "")

            condition_dict = json.loads(condition)
            start = condition_dict.get("start", "")
            # start_datetime = datetime.fromisoformat(start)
            start_datetime = datetime.strptime(start, "%Y-%m-%dT%H:%M:%S.%fZ")
            end = condition_dict.get("end", "")
            # end_datetime = datetime.fromisoformat(end)
            end_datetime = datetime.strptime(end, "%Y-%m-%dT%H:%M:%S.%fZ")
            print(f"{user}, {origin}, {condition_dict}, {start_datetime}, {end_datetime}")
            ack_ids.append(received_message.ack_id)


            if end_datetime < datetime.utcnow():
                print(f"access expired: {received_message.message}")
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


import os


class JitConfig:
    project_id: str
    pubsub_topic_name: str
    pubsub_subscription_path: str
    num_messages: int

    # init method or constructor
    def __init__(self, project_id, pubsub_topic_name, pubsub_subscription_path,
      num_messages):
        self.project_id = project_id
        self.pubsub_topic_name = pubsub_topic_name
        self.pubsub_subscription_path = pubsub_subscription_path
        self.num_messages = num_messages


def parse_env() -> JitConfig:
    """
    parse_env reads env var and return set it into JitConfig
    :return: JitConfig
    """
    project_id = os.environ['PROJECT_ID']
    pubsub_topic_name = os.environ['PUBSUB_TOPIC_NAME']
    pubsub_subscription_path = os.environ['PUBSUB_SUBSCRIPTION_PATH']
    num_messages = int(os.environ['NUM_MESSAGES'])

    return JitConfig(
      project_id=project_id,
      pubsub_topic_name=pubsub_topic_name,
      pubsub_subscription_path=pubsub_subscription_path,
      num_messages=num_messages,
    )

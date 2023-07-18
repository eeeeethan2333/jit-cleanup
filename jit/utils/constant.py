from enum import Enum

ACTIVATION_CONDITION_TITLE = "JIT access activation"


class MessageOrigin(Enum):
    APPROVAL = "jit-approval"
    BINDING = "jit-binding"
    ERROR = "jit-error"
    NOTIFICATION = "jit-notification"
    TEST = "jit-test"
    NOT_IMPLEMENTED = "not-implemented"

    @classmethod
    def from_str(cls, label):
        if label == "jit-approval":
            return cls.APPROVAL
        elif label == "jit-error":
            return cls.ERROR
        elif label == "jit-notification":
            return cls.NOTIFICATION
        elif label == "jit-binding":
            return cls.BINDING
        else:
            return cls.NOT_IMPLEMENTED

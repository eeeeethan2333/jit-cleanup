from enum import Enum


class MessageOrigin(Enum):
    APPROVAL = "jit-approval"
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
        else:
            return cls.NOT_IMPLEMENTED

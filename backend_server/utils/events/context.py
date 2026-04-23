from enum import Enum

class EventContext(Enum):
    TRIGGER_USER = "TRIGGER_USER"
    USER = "USER"
    GROUP = "GROUP"
    ACCOUNT = "ACCOUNT"
    ISO_TIMESTAMP = "ISO_TIMESTAMP"
    PACKAGES = "PACKAGES"
    SERVICE = "SERVICE"
    FILE = "FILE"
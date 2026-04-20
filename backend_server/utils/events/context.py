from enum import Enum

class EventContext(Enum):
    TRIGGER_USER = "TRIGGER_USER"
    USER = "USER"
    ISO_TIMESTAMP = "ISO_TIMESTAMP"
    PACKAGES = "PACKAGES"
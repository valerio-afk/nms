from enum import Enum

class DiskStatus(Enum):
    NEW       = 0
    ONLINE    = 1
    OFFLINE   = -1
    CORRUPTED = -2

class LogFilter(Enum):
    FRONTEND = 'frontend'
    BACKEND = 'backend'
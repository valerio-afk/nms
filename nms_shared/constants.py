import re
import os
from .msg import ErrorMessages, WarningMessages

POOLNAME='tank'
DATASETNAME='data'

KEYPATH='/root/tank.key'

APT_LISTS = "/var/lib/apt/lists"

ANSI_RESET = "\033[0m"
ANSI_COLOURS = {
    "DEBUG": "\033[36m",     # Cyan
    "INFO": "\033[32m",      # Green
    "WARNING": "\033[33m",   # Yellow
    "ERROR": "\033[31m",     # Red
    "CRITICAL": "\033[35m",  # Magenta
}

ANSI2HTML_MAP = {
    '0':  'reset',
    '1':  'bold',
    '4':  'underline',
    # foreground 30-37
    '30': 'fg-black',  '31': 'fg-red',   '32': 'fg-green', '33': 'fg-yellow',
    '34': 'fg-blue',   '35': 'fg-magenta','36': 'fg-cyan',  '37': 'fg-white',
    # background 40-47
    '40': 'bg-black',  '41': 'bg-red',   '42': 'bg-green', '43': 'bg-yellow',
    '44': 'bg-blue',   '45': 'bg-magenta','46': 'bg-cyan',  '47': 'bg-white',
    # bright foreground 90-97
    '90': 'fg-bright-black', '91': 'fg-bright-red', '92': 'fg-bright-green',
    '93': 'fg-bright-yellow','94': 'fg-bright-blue','95': 'fg-bright-magenta',
    '96': 'fg-bright-cyan',  '97': 'fg-bright-white',
    # bright backgrounds 100-107 (optional)
    '100': 'bg-bright-black','101': 'bg-bright-red','102': 'bg-bright-green',
    '103': 'bg-bright-yellow','104': 'bg-bright-blue','105': 'bg-bright-magenta',
    '106': 'bg-bright-cyan','107': 'bg-bright-white',
}

ANSI_RE = re.compile(r'\x1B\[(?P<code>[0-9;]*)m')

PORT_MIN = 1
PORT_MAX = 65535

SOCK_DIR = "/tmp"
SOCK_FILE= "privileged_cmdl.sock"

SOCK_PATH = os.path.join(SOCK_DIR,SOCK_FILE)

MSGID = {
    "ZFS-8000-2Q" : WarningMessages.W_POOL_OPENED,
    "ZFS-8000-3C" : ErrorMessages.E_POOL_OPENED,
    "ZFS-8000-4J" : WarningMessages.W_POOL_MISSING,
    "ZFS-8000-5E" : ErrorMessages.E_POOL_DISK_MISSING,
    "ZFS-8000-72" : ErrorMessages.E_POOL_CORRUPTED,
    "ZFS-8000-8A" : WarningMessages.W_POOL_CORRUPTED,
    "ZFS-8000-9P" : WarningMessages.W_DISK_ISSUE,
    "ZFS-8000-A5" : ErrorMessages.E_POOL_OUTDATED,
    "ZFS-8000-ER" : WarningMessages.W_DISK_FORMAT,
}

LANGS = {
    'en' : ('🇬🇧','English'),
    'it' : ('🇮🇹','Italiano')
}
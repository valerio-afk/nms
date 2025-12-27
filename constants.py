import re
import os

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

FILEBROWSER = {
    "database": "/opt/filebrowser/db",
    "config": "/opt/filebrowser/config"
}

MSGID = {
    "ZFS-8000-2Q" : ("warning", "One or more disks cannot be opened. As you have redundancy activated, you can still use your disk array. Run a diagnostic to see if the disk is getting faulted and replace if necessary. Alternatively, you can format it in the Advanced page."),
    "ZFS-8000-3C" : ("error", "One or more disks cannot be opened. Your disk array CANNOT be used in this state. Run a diagnostic to see if the disk is getting faulted and replace if necessary. Alternatively, you can format it in the Advanced page (this can likely cause data loss)."),
    "ZFS-8000-4J" : ("warning", "One or more disks seems missing. As you have redundancy activated, you can still use your disk array. Insert back the missing disk. If the disk is inserted and still see this error, you can format it in the Advanced page."),
    "ZFS-8000-5E" : ("error", "One or more disks seems missing. Your disk array CANNOT be used in this state. Insert back the missing disk. If the disk is inserted and still see this error, you can format it in the Advanced page (this can likely cause data loss)."),
    "ZFS-8000-72" : ("error", "The information related your disk array are corrupted. Recovery may be possible (but not guaranteed) and some data loss can occur. Use the `Attempt Recovery` button in Advanced. If the problem persists, back up your data, destroy and create a new array. Consider replacing one or more disks if their diagnostics suggest so."),
    "ZFS-8000-8A" : ("warning", "Some files and/or directories are corrupted and data cannot be recovered. If the problem persists, back up your data, destroy and create a new array. Consider replacing one or more disks if their diagnostics suggest so."),
    "ZFS-8000-9P" : ("warning", "One or more disks appear to experience some problems. No imminent actions are required at the moment. However, you should investigate which disk(s) is getting old and consider replacing it."),
    "ZFS-8000-A5" : ("error", "Your disk array seems to be too old and cannot be used anymore."),
    "ZFS-8000-ER" : ("warning", "Your disk array is experiencing some format issues. To solve this issue, press `Verify` in the Disk Management page."),
}
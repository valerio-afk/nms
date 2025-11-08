import logging
import sys
from datetime import datetime
from constants import ANSI_RESET, ANSI_COLOURS

class ColourFormatter(logging.Formatter):
    def format(self, record):
        color = ANSI_COLOURS.get(record.levelname, "")
        reset = ANSI_RESET

        # timestamp
        dt = datetime.fromtimestamp(record.created).strftime("%Y-%m-%d %H:%M:%S")

        # build message
        formatted = f"{color}[{record.name}] [{record.levelname}] [{dt}] {record.getMessage()}{reset}"
        return formatted

def setup_logger(name: str, level=logging.INFO):
    logger = logging.getLogger(name)
    logger.setLevel(level)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(ColourFormatter())

    logger.addHandler(handler)
    logger.propagate = False
    return logger

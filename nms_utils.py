import logging
import sys
from datetime import datetime
from constants import ANSI_RESET, ANSI_COLOURS
from pathlib import Path
import difflib

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

def read_lines_from_file(path,):
    return Path(path).read_text(encoding="utf-8", errors="surrogateescape").splitlines(keepends=True)


def make_diff(original_filename,modified_lines):
    orig_lines = read_lines_from_file(original_filename)
    diff_iter = difflib.unified_diff(
        orig_lines,
        modified_lines,
        fromfile=original_filename,
        tofile=original_filename,
        lineterm="\n"
    )
    return "".join(diff_iter)


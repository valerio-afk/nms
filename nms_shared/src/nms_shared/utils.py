from .constants import ANSI_RESET, ANSI_COLOURS,ANSI2HTML_MAP, ANSI_RE
from .enums import UserPermissions
from datetime import datetime
from logging import Logger
from pathlib import Path
from typing import List
import difflib
import logging
import sys


class ColourFormatter(logging.Formatter):
    def format(self, record):
        color = ANSI_COLOURS.get(record.levelname, "")
        reset = ANSI_RESET

        # timestamp
        dt = datetime.fromtimestamp(record.created).strftime("%Y-%m-%d %H:%M:%S")

        # build message
        formatted = f"{color}[{record.name}] [{record.levelname}] [{dt}] {record.getMessage()}{reset}"
        if record.exc_info:
            formatted += "\n" + self.formatException(record.exc_info)
        return formatted

def setup_logger(name: str, level=logging.INFO) -> Logger:
    logger = logging.getLogger(name)
    logger.setLevel(level)

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(ColourFormatter())

        logger.addHandler(handler)

    logger.propagate = False
    return logger

def read_lines_from_file(path:str) -> List[str]:
    return Path(path).read_text(encoding="utf-8", errors="surrogateescape").splitlines(keepends=True)


def make_diff_from_file(original_filename:str, modified_lines:List[str]) -> str:
    orig_lines = read_lines_from_file(original_filename)
    return make_diff(original_filename,orig_lines, modified_lines)

def make_diff(original_filename:str,original_lines:List[str], modified_lines:List[str]) -> str:
    diff_iter = difflib.unified_diff(
        original_lines,
        modified_lines,
        fromfile=original_filename,
        tofile=original_filename,
        lineterm="\n"
    )
    return "".join(diff_iter)

def ansi_to_html(text):

    # Keeps track of currently active classes: we will open and close spans.
    def repl(match):
        code = match.group('code')
        if code == '' or code == '0':
            # reset -> close all spans
            return '</span>' * 10  # cheap way: close up to N open spans (extra closes are tolerated)
        parts = code.split(';')
        classes = []
        for part in parts:
            if part in ANSI2HTML_MAP:
                classes.append(ANSI2HTML_MAP[part])
        if not classes:
            # unrecognized code -> no-op
            return ''
        class_str = ' '.join(classes)
        return f'<span class="{class_str}">'
    # Escape HTML special chars first, but keep newlines. We'll replace < and >.
    # NOTE: we will rely on Jinja's |safe only after we do manual escaping here to avoid XSS.
    esc = (text.replace('&', '&amp;')
                .replace('<', '&lt;')
                .replace('>', '&gt;'))
    # Convert ANSI sequences into span tags
    converted = ANSI_RE.sub(repl, esc)
    # Ensure all spans closed at the end
    converted += '</span>' * 10
    return converted


def match_permissions(user_permissions:List[str], target_permission:UserPermissions) -> bool:
    if "*" in user_permissions:
        return True

    parts = target_permission.value.split(".")

    for i in range(len(parts), 0, -1):
        candidate = ".".join(parts[:i])
        if candidate in user_permissions:
            return True

        wildcard = candidate + ".*"
        if wildcard in user_permissions:
            return True

    return False

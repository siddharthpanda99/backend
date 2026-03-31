"""
agents/runtime/utils/logging.py
---------------------------------
Colored logger factory shared across the runtime package.
"""
import sys
import logging


class _ColoredFormatter(logging.Formatter):
    _CYAN   = "\033[96m"
    _GREEN  = "\033[92m"
    _YELLOW = "\033[93m"
    _RED    = "\033[91m"
    _RESET  = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        msg = super().format(record)
        if record.levelno >= logging.ERROR:
            return f"{self._RED}{msg}{self._RESET}"
        if record.levelno >= logging.WARNING:
            return f"{self._YELLOW}{msg}{self._RESET}"
        if "node" in msg.lower() or "stream" in msg.lower():
            return f"{self._CYAN}{msg}{self._RESET}"
        if "tool" in msg.lower():
            return f"{self._GREEN}{msg}{self._RESET}"
        return msg


def get_logger(name: str) -> logging.Logger:
    """Return a named, colored console logger. Safe to call multiple times."""
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(
            _ColoredFormatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        )
        logger.addHandler(handler)
    return logger

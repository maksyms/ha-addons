import logging
import os
import sys


def setup(adapter_name: str) -> logging.Logger:
    """Configure logging for an adapter.

    Reads LOG_LEVEL from environment (default: info).
    Logs to stdout so HA captures output in add-on logs.
    """
    level_name = os.environ.get("LOG_LEVEL", "info").upper()
    level = getattr(logging, level_name, logging.INFO)

    logger = logging.getLogger(adapter_name)
    logger.setLevel(level)

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(level)
        formatter = logging.Formatter(
            f"%(asctime)s [{adapter_name}] %(levelname)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger

"""
Logging configuration utilities.

This module defines a simple helper to configure Python's logging module
with a consistent format. In larger applications you may wish to use
``logging.config.dictConfig`` with a full configuration dictionary,
but for the base edge node a basic configuration is sufficient.
"""

import logging
from typing import Optional


def setup_logging(level: int = logging.INFO, log_file: Optional[str] = None) -> None:
    """Configure root logger with a basic formatter.

    Parameters
    ----------
    level: int
        Logging level (e.g. ``logging.INFO``).
    log_file: Optional[str]
        Optional file path to log to. If provided, logs are also written to
        the specified file.
    """
    handlers = [logging.StreamHandler()]
    if log_file:
        handlers.append(logging.FileHandler(log_file))
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=handlers,
    )
"""
Logging configuration for the Stochastic RSI system
"""
import logging
import sys
from config import LOG_LEVEL, LOG_FORMAT


def setup_logger(name):
    """
    Set up and return a logger with specified configuration

    Args:
        name: Name of the logger

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, LOG_LEVEL))

    # Create console handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(getattr(logging, LOG_LEVEL))

    # Create formatter
    formatter = logging.Formatter(LOG_FORMAT)
    handler.setFormatter(formatter)

    # Add handler to logger
    if not logger.handlers:
        logger.addHandler(handler)

    return logger

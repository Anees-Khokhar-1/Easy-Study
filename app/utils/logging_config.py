"""
Centralized logging configuration using Loguru.
Import `logger` from this module across all backend files.
"""

import sys
from loguru import logger

# Remove default handler and add custom ones
logger.remove()

# Console – colored, concise
logger.add(
    sys.stdout,
    format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{module}</cyan>:<cyan>{function}</cyan> – <level>{message}</level>",
    level="INFO",
    colorize=True,
)

# File – rotated, detailed
logger.add(
    "./data/logs/easy-study_{time:YYYY-MM-DD}.log",
    rotation="5 MB",
    retention="7 days",
    format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {module}:{function}:{line} – {message}",
    level="DEBUG",
    backtrace=True,
    diagnose=True,
)

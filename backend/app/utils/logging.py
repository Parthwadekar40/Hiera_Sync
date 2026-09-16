import logging
import sys
from app.config.settings import settings

def setup_logger():
    # Avoid duplicate handlers
    logger = logging.getLogger("hierasync")
    if not logger.hasHandlers():
        # Read log level from settings or default to INFO
        log_level = getattr(settings, "LOG_LEVEL", "INFO").upper()
        level = getattr(logging, log_level, logging.INFO)
        logger.setLevel(level)

        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        
        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    return logger

logger = setup_logger()

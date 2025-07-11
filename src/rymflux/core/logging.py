import logging
import os
from typing import Optional

def setup_logging(debug: bool = False) -> None:
    """Configure logging with a debug level toggle."""
    level = logging.DEBUG if debug or os.environ.get("RYMFLUX_DEBUG", "false").lower() == "true" else logging.WARNING
    logging.basicConfig(
        level=level,
        format="%(levelname)s - %(message)s",
        handlers=[logging.StreamHandler()]
    )

def get_logger(name: str) -> logging.Logger:
    """Return a logger instance with the given name."""
    return logging.getLogger(name)
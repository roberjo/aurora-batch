"""Utility functions for the replication system."""

import json
import logging
import os
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)


def get_correlation_id() -> str:
    """Generate a correlation ID for request tracking."""
    return str(uuid.uuid4())


def get_environment_variable(key: str, default: Optional[str] = None) -> str:
    """Get environment variable with error handling."""
    value = os.getenv(key, default)
    if value is None:
        raise ValueError(f"Environment variable {key} is required but not set")
    return value


def log_event(level: str, message: str, correlation_id: str, **kwargs: Any) -> None:
    """Log structured event with correlation ID."""
    log_data = {
        "correlation_id": correlation_id,
        "message": message,
        "timestamp": datetime.utcnow().isoformat(),
        **kwargs
    }
    
    log_message = json.dumps(log_data)
    
    if level.upper() == "ERROR":
        logger.error(log_message)
    elif level.upper() == "WARNING":
        logger.warning(log_message)
    elif level.upper() == "INFO":
        logger.info(log_message)
    else:
        logger.debug(log_message)


def create_response(status_code: int, message: str, correlation_id: str, **kwargs: Any) -> Dict[str, Any]:
    """Create a standardized response dictionary."""
    return {
        "statusCode": status_code,
        "correlation_id": correlation_id,
        "message": message,
        "timestamp": datetime.utcnow().isoformat(),
        **kwargs
    }


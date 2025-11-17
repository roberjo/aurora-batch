"""Lambda function for S3 cleanup maintenance."""

import json
import logging
import os
from typing import Any, Dict

try:
    from s3_cleanup import S3Cleanup
    from utils import create_response, get_correlation_id, log_event
except ImportError:
    # For local development/testing
    from .s3_cleanup import S3Cleanup
    from .utils import create_response, get_correlation_id, log_event

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda function handler for S3 cleanup maintenance.

    Event structure:
    {
        "action": "cleanup_old" | "cleanup_orphaned" | "stats",
        "older_than_days": 7,  # For cleanup_old
        "max_age_hours": 24,   # For cleanup_orphaned
        "schema_name": "public",  # Optional filter
        "table_name": "customers",  # Optional filter
        "dry_run": true  # Optional, default false
    }
    """
    correlation_id = get_correlation_id()

    try:
        log_event('INFO', 'S3 cleanup Lambda started', correlation_id,
                 event=json.dumps(event) if event else '{}')

        bucket_name = os.getenv('S3_STAGE_BUCKET')
        prefix = os.getenv('S3_STAGE_PREFIX', 'staging')

        if not bucket_name:
            raise ValueError("S3_STAGE_BUCKET environment variable is required")

        cleanup = S3Cleanup(bucket_name=bucket_name, prefix=prefix)
        action = event.get('action', 'stats')
        dry_run = event.get('dry_run', False)

        if action == 'stats':
            stats = cleanup.get_bucket_stats()
            log_event('INFO', 'Bucket statistics retrieved', correlation_id, stats=stats)
            return create_response(
                status_code=200,
                message='Bucket statistics retrieved',
                correlation_id=correlation_id,
                stats=stats
            )

        elif action == 'cleanup_old':
            older_than_days = event.get('older_than_days', 7)
            schema_name = event.get('schema_name')
            table_name = event.get('table_name')

            result = cleanup.delete_old_files(
                older_than_days=older_than_days,
                schema_name=schema_name,
                table_name=table_name,
                dry_run=dry_run
            )

            log_event('INFO', 'Old files cleanup completed', correlation_id, result=result)
            return create_response(
                status_code=200,
                message='Old files cleanup completed',
                correlation_id=correlation_id,
                result=result
            )

        elif action == 'cleanup_orphaned':
            max_age_hours = event.get('max_age_hours', 24)

            result = cleanup.cleanup_orphaned_files(
                max_age_hours=max_age_hours,
                dry_run=dry_run
            )

            log_event('INFO', 'Orphaned files cleanup completed', correlation_id, result=result)
            return create_response(
                status_code=200,
                message='Orphaned files cleanup completed',
                correlation_id=correlation_id,
                result=result
            )

        else:
            raise ValueError(f"Unknown action: {action}. Must be 'stats', 'cleanup_old', or 'cleanup_orphaned'")

    except Exception as e:
        error_message = f"S3 cleanup Lambda failed: {str(e)}"
        log_event('ERROR', error_message, correlation_id, error=str(e))

        return create_response(
            status_code=500,
            message=error_message,
            correlation_id=correlation_id,
            error=str(e)
        )


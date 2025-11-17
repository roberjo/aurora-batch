"""S3 cleanup utility for orphaned files and maintenance."""

import logging
import os
from datetime import datetime, timedelta
from typing import List, Optional

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


class S3Cleanup:
    """Utility for cleaning up S3 staging files."""

    def __init__(self, bucket_name: str, prefix: str = "staging"):
        """
        Initialize S3 cleanup utility.

        Args:
            bucket_name: S3 bucket name
            prefix: S3 prefix/path
        """
        self.bucket_name = bucket_name
        self.prefix = prefix.rstrip('/')
        self.s3_client = boto3.client('s3')

    def list_old_files(self, older_than_days: int = 7, 
                      schema_name: Optional[str] = None,
                      table_name: Optional[str] = None) -> List[dict]:
        """
        List files older than specified days.

        Args:
            older_than_days: Age threshold in days
            schema_name: Optional schema filter
            table_name: Optional table filter

        Returns:
            List of file objects with metadata
        """
        cutoff_date = datetime.utcnow() - timedelta(days=older_than_days)
        old_files = []

        prefix = f"{self.prefix}/"
        if schema_name:
            prefix = f"{prefix}{schema_name}/"
        if table_name:
            prefix = f"{prefix}{table_name}/"

        try:
            paginator = self.s3_client.get_paginator('list_objects_v2')
            pages = paginator.paginate(Bucket=self.bucket_name, Prefix=prefix)

            for page in pages:
                if 'Contents' not in page:
                    continue

                for obj in page['Contents']:
                    # Check file age
                    if obj['LastModified'].replace(tzinfo=None) < cutoff_date:
                        old_files.append({
                            'key': obj['Key'],
                            'size': obj['Size'],
                            'last_modified': obj['LastModified'].isoformat(),
                            'age_days': (datetime.utcnow() - obj['LastModified'].replace(tzinfo=None)).days
                        })

            logger.info(f"Found {len(old_files)} files older than {older_than_days} days")
            return old_files

        except ClientError as e:
            logger.error(f"Failed to list old files: {str(e)}")
            return []

    def delete_old_files(self, older_than_days: int = 7,
                        schema_name: Optional[str] = None,
                        table_name: Optional[str] = None,
                        dry_run: bool = True) -> dict:
        """
        Delete files older than specified days.

        Args:
            older_than_days: Age threshold in days
            schema_name: Optional schema filter
            table_name: Optional table filter
            dry_run: If True, only report what would be deleted

        Returns:
            Dictionary with deletion summary
        """
        old_files = self.list_old_files(older_than_days, schema_name, table_name)

        if not old_files:
            return {
                'files_found': 0,
                'files_deleted': 0,
                'total_size_bytes': 0,
                'dry_run': dry_run
            }

        total_size = sum(f['size'] for f in old_files)
        deleted_count = 0

        if dry_run:
            logger.info(f"DRY RUN: Would delete {len(old_files)} files ({total_size / 1024 / 1024:.2f} MB)")
            return {
                'files_found': len(old_files),
                'files_deleted': 0,
                'total_size_bytes': total_size,
                'dry_run': True,
                'files': old_files
            }

        # Delete files
        for file_info in old_files:
            try:
                self.s3_client.delete_object(
                    Bucket=self.bucket_name,
                    Key=file_info['key']
                )
                deleted_count += 1
                logger.info(f"Deleted old file: {file_info['key']}")
            except ClientError as e:
                logger.error(f"Failed to delete file {file_info['key']}: {str(e)}")

        logger.info(f"Deleted {deleted_count} old files ({total_size / 1024 / 1024:.2f} MB)")

        return {
            'files_found': len(old_files),
            'files_deleted': deleted_count,
            'total_size_bytes': total_size,
            'dry_run': False
        }

    def get_bucket_stats(self) -> dict:
        """
        Get statistics about the S3 bucket.

        Returns:
            Dictionary with bucket statistics
        """
        try:
            total_size = 0
            total_files = 0
            files_by_schema = {}
            files_by_table = {}

            paginator = self.s3_client.get_paginator('list_objects_v2')
            pages = paginator.paginate(Bucket=self.bucket_name, Prefix=self.prefix)

            for page in pages:
                if 'Contents' not in page:
                    continue

                for obj in page['Contents']:
                    total_size += obj['Size']
                    total_files += 1

                    # Parse schema/table from key
                    key_parts = obj['Key'].replace(f"{self.prefix}/", "").split('/')
                    if len(key_parts) >= 1:
                        schema = key_parts[0]
                        files_by_schema[schema] = files_by_schema.get(schema, 0) + 1

                    if len(key_parts) >= 2:
                        table = key_parts[1]
                        files_by_table[f"{schema}.{table}"] = files_by_table.get(f"{schema}.{table}", 0) + 1

            return {
                'total_files': total_files,
                'total_size_bytes': total_size,
                'total_size_mb': total_size / 1024 / 1024,
                'total_size_gb': total_size / 1024 / 1024 / 1024,
                'files_by_schema': files_by_schema,
                'files_by_table': files_by_table
            }

        except ClientError as e:
            logger.error(f"Failed to get bucket stats: {str(e)}")
            return {}

    def cleanup_orphaned_files(self, max_age_hours: int = 24, dry_run: bool = True) -> dict:
        """
        Clean up orphaned files (files that were uploaded but never loaded).

        Args:
            max_age_hours: Maximum age in hours before considering file orphaned
            dry_run: If True, only report what would be deleted

        Returns:
            Dictionary with cleanup summary
        """
        cutoff_time = datetime.utcnow() - timedelta(hours=max_age_hours)
        orphaned_files = []

        try:
            paginator = self.s3_client.get_paginator('list_objects_v2')
            pages = paginator.paginate(Bucket=self.bucket_name, Prefix=self.prefix)

            for page in pages:
                if 'Contents' not in page:
                    continue

                for obj in page['Contents']:
                    # Check if file is old enough to be considered orphaned
                    if obj['LastModified'].replace(tzinfo=None) < cutoff_time:
                        # Files older than max_age_hours without being loaded are orphaned
                        orphaned_files.append({
                            'key': obj['Key'],
                            'size': obj['Size'],
                            'last_modified': obj['LastModified'].isoformat(),
                            'age_hours': (datetime.utcnow() - obj['LastModified'].replace(tzinfo=None)).total_seconds() / 3600
                        })

            if not orphaned_files:
                return {
                    'orphaned_files_found': 0,
                    'orphaned_files_deleted': 0,
                    'total_size_bytes': 0,
                    'dry_run': dry_run
                }

            total_size = sum(f['size'] for f in orphaned_files)

            if dry_run:
                logger.info(f"DRY RUN: Would delete {len(orphaned_files)} orphaned files ({total_size / 1024 / 1024:.2f} MB)")
                return {
                    'orphaned_files_found': len(orphaned_files),
                    'orphaned_files_deleted': 0,
                    'total_size_bytes': total_size,
                    'dry_run': True,
                    'files': orphaned_files
                }

            # Delete orphaned files
            deleted_count = 0
            for file_info in orphaned_files:
                try:
                    self.s3_client.delete_object(
                        Bucket=self.bucket_name,
                        Key=file_info['key']
                    )
                    deleted_count += 1
                    logger.info(f"Deleted orphaned file: {file_info['key']}")
                except ClientError as e:
                    logger.error(f"Failed to delete orphaned file {file_info['key']}: {str(e)}")

            logger.info(f"Deleted {deleted_count} orphaned files ({total_size / 1024 / 1024:.2f} MB)")

            return {
                'orphaned_files_found': len(orphaned_files),
                'orphaned_files_deleted': deleted_count,
                'total_size_bytes': total_size,
                'dry_run': False
            }

        except ClientError as e:
            logger.error(f"Failed to cleanup orphaned files: {str(e)}")
            return {}


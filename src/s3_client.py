"""S3 client for staging data files."""

import csv
import json
import logging
import os
from datetime import datetime
from io import StringIO
from typing import Dict, List, Optional

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


class S3Client:
    """Client for uploading data files to S3 for Snowflake staging."""

    def __init__(self, bucket_name: str, prefix: str = "staging", file_format: str = "csv"):
        """
        Initialize S3 client.

        Args:
            bucket_name: S3 bucket name
            prefix: S3 prefix/path for files
            file_format: File format ('csv' or 'parquet')
        """
        self.bucket_name = bucket_name
        self.prefix = prefix.rstrip('/')
        self.file_format = file_format.lower()
        self.s3_client = boto3.client('s3')

    def upload_batch(self, data: List[Dict], schema_name: str, table_name: str,
                    batch_number: int, correlation_id: str = '') -> str:
        """
        Upload a batch of data to S3.

        Args:
            data: List of dictionaries representing rows
            schema_name: Schema name
            table_name: Table name
            batch_number: Batch number for file naming
            correlation_id: Correlation ID for logging

        Returns:
            S3 key/path of uploaded file
        """
        if not data:
            raise ValueError("Cannot upload empty batch")

        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        file_name = f"{schema_name}_{table_name}_batch{batch_number}_{timestamp}.{self.file_format}"
        s3_key = f"{self.prefix}/{schema_name}/{table_name}/{file_name}"

        try:
            if self.file_format == 'csv':
                file_content = self._convert_to_csv(data)
                content_type = 'text/csv'
            elif self.file_format == 'parquet':
                file_content = self._convert_to_parquet(data)
                content_type = 'application/parquet'
            else:
                raise ValueError(f"Unsupported file format: {self.file_format}")

            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=s3_key,
                Body=file_content,
                ContentType=content_type,
                ServerSideEncryption='AES256',
                Metadata={
                    'schema': schema_name,
                    'table': table_name,
                    'batch_number': str(batch_number),
                    'row_count': str(len(data)),
                    'correlation_id': correlation_id,
                    'timestamp': timestamp
                }
            )

            logger.info(f"Uploaded batch {batch_number} to S3: s3://{self.bucket_name}/{s3_key}",
                       extra={'correlation_id': correlation_id, 's3_key': s3_key, 'rows': len(data)})

            return s3_key

        except ClientError as e:
            logger.error(f"Failed to upload batch to S3: {str(e)}",
                        extra={'correlation_id': correlation_id, 's3_key': s3_key})
            raise

    def _convert_to_csv(self, data: List[Dict]) -> bytes:
        """Convert data to CSV format."""
        if not data:
            return b''

        # Get column names from first row
        fieldnames = list(data[0].keys())
        
        # Create CSV in memory
        output = StringIO()
        writer = csv.DictWriter(output, fieldnames=fieldnames, quoting=csv.QUOTE_MINIMAL)
        writer.writeheader()
        
        for row in data:
            # Convert None to empty string, handle special characters
            cleaned_row = {}
            for key, value in row.items():
                if value is None:
                    cleaned_row[key] = ''
                elif isinstance(value, (dict, list)):
                    cleaned_row[key] = json.dumps(value)
                else:
                    cleaned_row[key] = str(value)
            writer.writerow(cleaned_row)
        
        return output.getvalue().encode('utf-8')

    def _convert_to_parquet(self, data: List[Dict]) -> bytes:
        """Convert data to Parquet format."""
        try:
            import pandas as pd
            import pyarrow as pa
            import pyarrow.parquet as pq
        except ImportError:
            raise ImportError("Parquet format requires pandas and pyarrow. Install with: pip install pandas pyarrow")

        # Convert to DataFrame
        df = pd.DataFrame(data)
        
        # Convert to Parquet
        table = pa.Table.from_pandas(df)
        buffer = pa.BufferOutputStream()
        pq.write_table(table, buffer)
        
        return buffer.getvalue().to_pybytes()

    def delete_file(self, s3_key: str, correlation_id: str = '') -> None:
        """
        Delete a file from S3.

        Args:
            s3_key: S3 key/path of file to delete
            correlation_id: Correlation ID for logging
        """
        try:
            self.s3_client.delete_object(
                Bucket=self.bucket_name,
                Key=s3_key
            )
            logger.info(f"Deleted file from S3: s3://{self.bucket_name}/{s3_key}",
                       extra={'correlation_id': correlation_id, 's3_key': s3_key})
        except ClientError as e:
            logger.error(f"Failed to delete file from S3: {str(e)}",
                        extra={'correlation_id': correlation_id, 's3_key': s3_key})
            # Don't raise - deletion failure is not critical

    def list_files(self, schema_name: str, table_name: str, 
                  prefix_filter: Optional[str] = None) -> List[str]:
        """
        List files in S3 for a given table.

        Args:
            schema_name: Schema name
            table_name: Table name
            prefix_filter: Optional prefix filter

        Returns:
            List of S3 keys
        """
        prefix = f"{self.prefix}/{schema_name}/{table_name}/"
        if prefix_filter:
            prefix = f"{prefix}{prefix_filter}"

        try:
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=prefix
            )

            if 'Contents' not in response:
                return []

            return [obj['Key'] for obj in response['Contents']]

        except ClientError as e:
            logger.error(f"Failed to list files in S3: {str(e)}")
            return []


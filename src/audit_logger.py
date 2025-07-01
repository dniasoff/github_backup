import json
import logging
import os
import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, List
from decimal import Decimal
import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

def convert_decimals(obj):
    """Convert DynamoDB Decimal objects to int/float for JSON serialization."""
    if isinstance(obj, Decimal):
        if obj % 1 == 0:
            return int(obj)
        else:
            return float(obj)
    elif isinstance(obj, dict):
        return {k: convert_decimals(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_decimals(v) for v in obj]
    return obj

class AuditLogger:
    """
    Centralized audit logging for GitHub backup operations.
    Logs all events to DynamoDB for comprehensive audit trail.
    """
    
    def __init__(self):
        self.dynamodb = boto3.resource('dynamodb')
        self.events_table = self.dynamodb.Table('github-backup-events')
        self.history_table = self.dynamodb.Table('github-backup-repository-history')
        self.download_table = self.dynamodb.Table('github-backup-download-operations')
        self.glacier_table = self.dynamodb.Table('github-backup-glacier-jobs')
    
    def log_backup_event(self, 
                        repository_name: str,
                        event_type: str,
                        status: str,
                        details: Dict[str, Any],
                        error: Optional[str] = None) -> str:
        """
        Log a backup-related event to the audit trail.
        
        Args:
            repository_name: Name of the repository
            event_type: Type of event (backup, discovery, archival, etc.)
            status: Event status (started, completed, failed)
            details: Additional event details
            error: Error message if status is failed
            
        Returns:
            Event ID for tracking
        """
        try:
            event_id = str(uuid.uuid4())
            timestamp = datetime.now(timezone.utc).isoformat()
            date_partition = datetime.now(timezone.utc).strftime('%Y-%m-%d')
            
            item = {
                'event_id': event_id,
                'timestamp': timestamp,
                'date_partition': date_partition,
                'repository_name': repository_name,
                'event_type': event_type,
                'status': status,
                'details': details,
                'lambda_function': os.environ.get('AWS_LAMBDA_FUNCTION_NAME', 'unknown'),
                'execution_id': os.environ.get('AWS_LAMBDA_LOG_STREAM_NAME', 'unknown')
            }
            
            if error:
                item['error'] = error
            
            self.events_table.put_item(Item=item)
            logger.info(f"Logged audit event: {event_id} for {repository_name}")
            return event_id
            
        except ClientError as e:
            logger.error(f"Failed to log audit event: {str(e)}")
            return ""
    
    def log_repository_backup(self,
                            repository_name: str,
                            backup_version: str,
                            s3_key: str,
                            size_bytes: int,
                            storage_class: str = 's3',
                            metadata: Optional[Dict[str, Any]] = None) -> None:
        """
        Log repository backup metadata to history table.
        
        Args:
            repository_name: Name of the repository
            backup_version: Backup version identifier (timestamp)
            s3_key: S3 object key for the backup
            size_bytes: Size of the backup in bytes
            storage_class: Storage class (s3, glacier, deep-archive)
            metadata: Additional backup metadata
        """
        try:
            timestamp = datetime.now(timezone.utc).isoformat()
            
            item = {
                'repository_name': repository_name,
                'backup_version': backup_version,
                'timestamp': timestamp,
                's3_key': s3_key,
                'size_bytes': size_bytes,
                'storage_class': storage_class,
                'backup_date': backup_version.split('/')[1] if '/' in backup_version else backup_version[:10]
            }
            
            if metadata:
                item['metadata'] = metadata
            
            self.history_table.put_item(Item=item)
            logger.info(f"Logged repository backup: {repository_name} version {backup_version}")
            
        except ClientError as e:
            logger.error(f"Failed to log repository backup: {str(e)}")
    
    def create_download_operation(self,
                                repository_name: str,
                                backup_version: str,
                                user_id: str,
                                download_type: str,
                                source_location: str) -> str:
        """
        Create a new download operation record.
        
        Args:
            repository_name: Name of the repository to download
            backup_version: Version of backup to download
            user_id: User initiating the download
            download_type: Type of download (s3_direct, glacier_retrieval)
            source_location: S3 key or Glacier archive ID
            
        Returns:
            Download operation ID
        """
        try:
            download_id = str(uuid.uuid4())
            timestamp = datetime.now(timezone.utc).isoformat()
            expires_at = int((datetime.now(timezone.utc).timestamp() + (30 * 24 * 60 * 60)))  # 30 days TTL
            
            item = {
                'download_id': download_id,
                'repository_name': repository_name,
                'backup_version': backup_version,
                'user_id': user_id,
                'download_type': download_type,
                'source_location': source_location,
                'status': 'requested',
                'created_at': timestamp,
                'expires_at': expires_at
            }
            
            self.download_table.put_item(Item=item)
            logger.info(f"Created download operation: {download_id} for {repository_name}")
            return download_id
            
        except ClientError as e:
            logger.error(f"Failed to create download operation: {str(e)}")
            return ""
    
    def update_download_status(self,
                             download_id: str,
                             status: str,
                             details: Optional[Dict[str, Any]] = None,
                             error: Optional[str] = None) -> None:
        """
        Update the status of a download operation.
        
        Args:
            download_id: Download operation ID
            status: New status (in_progress, completed, failed)
            details: Additional status details
            error: Error message if status is failed
        """
        try:
            timestamp = datetime.now(timezone.utc).isoformat()
            
            update_expression = "SET #status = :status, updated_at = :timestamp"
            expression_values = {
                ':status': status,
                ':timestamp': timestamp
            }
            expression_names = {'#status': 'status'}
            
            if details:
                update_expression += ", details = :details"
                expression_values[':details'] = details
            
            if error:
                update_expression += ", #error = :error"
                expression_values[':error'] = error
                expression_names['#error'] = 'error'
            
            self.download_table.update_item(
                Key={'download_id': download_id},
                UpdateExpression=update_expression,
                ExpressionAttributeValues=expression_values,
                ExpressionAttributeNames=expression_names
            )
            
            logger.info(f"Updated download operation {download_id} to status: {status}")
            
        except ClientError as e:
            logger.error(f"Failed to update download status: {str(e)}")
    
    def log_glacier_job(self,
                       job_id: str,
                       repository_name: str,
                       archive_id: str,
                       job_type: str = 'archive-retrieval') -> None:
        """
        Log a Glacier retrieval job.
        
        Args:
            job_id: AWS Glacier job ID
            repository_name: Repository being retrieved
            archive_id: Glacier archive ID
            job_type: Type of Glacier job
        """
        try:
            timestamp = datetime.now(timezone.utc).isoformat()
            expires_at = int((datetime.now(timezone.utc).timestamp() + (30 * 24 * 60 * 60)))  # 30 days TTL
            
            item = {
                'job_id': job_id,
                'repository_name': repository_name,
                'archive_id': archive_id,
                'job_type': job_type,
                'status': 'InProgress',
                'created_at': timestamp,
                'expires_at': expires_at
            }
            
            self.glacier_table.put_item(Item=item)
            logger.info(f"Logged Glacier job: {job_id} for {repository_name}")
            
        except ClientError as e:
            logger.error(f"Failed to log Glacier job: {str(e)}")
    
    def update_glacier_job_status(self,
                                job_id: str,
                                status: str,
                                details: Optional[Dict[str, Any]] = None) -> None:
        """
        Update Glacier job status.
        
        Args:
            job_id: Glacier job ID
            status: Job status (InProgress, Succeeded, Failed)
            details: Additional job details
        """
        try:
            timestamp = datetime.now(timezone.utc).isoformat()
            
            update_expression = "SET #status = :status, updated_at = :timestamp"
            expression_values = {
                ':status': status,
                ':timestamp': timestamp
            }
            expression_names = {'#status': 'status'}
            
            if details:
                update_expression += ", details = :details"
                expression_values[':details'] = details
            
            self.glacier_table.update_item(
                Key={'job_id': job_id},
                UpdateExpression=update_expression,
                ExpressionAttributeValues=expression_values,
                ExpressionAttributeNames=expression_names
            )
            
            logger.info(f"Updated Glacier job {job_id} to status: {status}")
            
        except ClientError as e:
            logger.error(f"Failed to update Glacier job status: {str(e)}")
    
    def get_repository_history(self, repository_name: str, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get backup history for a repository.
        
        Args:
            repository_name: Repository name
            limit: Maximum number of records to return
            
        Returns:
            List of backup history records
        """
        try:
            response = self.history_table.query(
                KeyConditionExpression='repository_name = :repo_name',
                ExpressionAttributeValues={':repo_name': repository_name},
                ScanIndexForward=False,  # Sort by backup_version descending
                Limit=limit
            )
            items = response.get('Items', [])
            return [convert_decimals(item) for item in items]
            
        except ClientError as e:
            logger.error(f"Failed to get repository history: {str(e)}")
            return []
    
    def get_recent_events(self, hours: int = 24, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get recent audit events with proper pagination.
        
        Args:
            hours: Number of hours to look back
            limit: Maximum number of events to return
            
        Returns:
            List of recent events
        """
        try:
            # Calculate time cutoff
            cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)
            cutoff_timestamp = cutoff_time.isoformat()
            
            # Use scan to get all events from today within the time window
            date_partition = datetime.now(timezone.utc).strftime('%Y-%m-%d')
            
            items = []
            scan_kwargs = {
                'FilterExpression': 'date_partition = :date_partition AND #timestamp >= :cutoff',
                'ExpressionAttributeValues': {
                    ':date_partition': date_partition,
                    ':cutoff': cutoff_timestamp
                },
                'ExpressionAttributeNames': {'#timestamp': 'timestamp'}
            }
            
            # Paginate through all results
            while True:
                response = self.events_table.scan(**scan_kwargs)
                items.extend(response.get('Items', []))
                
                # Check if we have enough items or if there's more data
                if len(items) >= limit * 2 or 'LastEvaluatedKey' not in response:
                    break
                    
                # Set up for next page
                scan_kwargs['ExclusiveStartKey'] = response['LastEvaluatedKey']
            
            # Sort by timestamp descending and limit
            items.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
            items = items[:limit]
            
            logger.info(f"Retrieved {len(items)} events from last {hours} hours (requested limit: {limit})")
            
            return [convert_decimals(item) for item in items]
            
        except ClientError as e:
            logger.error(f"Failed to get recent events: {str(e)}")
            return []

# Global audit logger instance
audit_logger = AuditLogger()
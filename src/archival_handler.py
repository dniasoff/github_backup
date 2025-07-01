import json
import logging
import os
import tarfile
import tempfile
from datetime import datetime, timedelta
from typing import Dict, List, Any
import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def lambda_handler(event: Dict[str, Any], context) -> Dict[str, Any]:
    """
    Lambda function to handle archival operations.
    Can list backups to archive or archive a single backup (called by Step Functions).
    """
    try:
        s3_bucket = os.environ['S3_BUCKET_NAME']
        glacier_vault = os.environ['GLACIER_VAULT_NAME']
        retention_days = int(event.get('retention_days_override', os.environ.get('RETENTION_DAYS', '30')))
        
        action = event.get('action', 'list')
        
        logger.info(f"Archival action: {action}, bucket: {s3_bucket}, retention_days: {retention_days}")
        
        if action == 'list':
            # List all backups that need to be archived
            backups_to_archive = list_backups_to_archive(s3_bucket, retention_days)
            logger.info(f"Found {len(backups_to_archive)} backups to archive")
            return {
                'backups': backups_to_archive
            }
        
        elif action == 'archive':
            # Archive a single backup (called by Step Functions Map state)
            backup_info = event.get('backup')
            if not backup_info:
                raise ValueError("Backup info must be provided for archive action")
            
            result = archive_single_backup(s3_bucket, glacier_vault, backup_info)
            return result
        
        else:
            raise ValueError(f"Unknown action: {action}")
        
    except Exception as e:
        logger.error(f"Error during archival process: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }

def list_backups_to_archive(bucket: str, retention_days: int) -> List[Dict[str, Any]]:
    """
    List all backup files that are older than retention period and need archiving.
    Current S3 structure: nightly/repository-name/YYYY-MM-DD-HH-MM.tar.gz
    """
    s3_client = boto3.client('s3')
    cutoff_date = datetime.now() - timedelta(days=retention_days)
    backups_to_archive = []
    
    try:
        paginator = s3_client.get_paginator('list_objects_v2')
        pages = paginator.paginate(Bucket=bucket, Prefix='nightly/')
        
        for page in pages:
            for obj in page.get('Contents', []):
                if obj['Key'].endswith('.tar.gz'):
                    # Current structure: nightly/repository-name/YYYY-MM-DD-HH-MM.tar.gz
                    key_parts = obj['Key'].split('/')
                    if len(key_parts) >= 3:
                        repository_name = key_parts[1]
                        backup_filename = key_parts[2]
                        
                        # Parse date/time from filename: YYYY-MM-DD-HH-MM.tar.gz
                        backup_date = None
                        try:
                            # Remove .tar.gz extension and parse datetime
                            filename_without_ext = backup_filename.replace('.tar.gz', '')
                            if len(filename_without_ext) >= 16:  # YYYY-MM-DD-HH-MM
                                # Parse: 2025-07-01-21-30
                                date_time_str = filename_without_ext[:16]
                                backup_date = datetime.strptime(date_time_str, '%Y-%m-%d-%H-%M')
                            else:
                                # Fallback: try just date part YYYY-MM-DD
                                date_part = filename_without_ext[:10]
                                backup_date = datetime.strptime(date_part, '%Y-%m-%d')
                        except ValueError:
                            # If filename parsing fails, use file's LastModified date
                            backup_date = obj['LastModified'].replace(tzinfo=None)
                            logger.warning(f"Could not parse date from filename {backup_filename}, using LastModified date")
                        
                        # Check if backup is older than retention period
                        if backup_date and backup_date < cutoff_date:
                            backups_to_archive.append({
                                'key': obj['Key'],
                                'repository_name': repository_name,
                                'backup_filename': backup_filename,
                                'size': obj['Size'],
                                'date': backup_date.isoformat(),
                                'last_modified': obj['LastModified'].isoformat(),
                                'age_days': (datetime.now() - backup_date).days
                            })
                            
                            logger.info(f"Found backup to archive: {obj['Key']} (age: {(datetime.now() - backup_date).days} days)")
    
    except Exception as e:
        logger.error(f"Error listing backups to archive: {str(e)}")
    
    logger.info(f"Found {len(backups_to_archive)} backups older than {retention_days} days to archive")
    return backups_to_archive

def archive_single_backup(bucket: str, glacier_vault: str, backup_info: Dict[str, Any]) -> Dict[str, Any]:
    """
    Archive a single backup file to Glacier and remove from S3.
    """
    s3_client = boto3.client('s3')
    glacier_client = boto3.client('glacier')
    
    backup_key = backup_info['key']
    
    try:
        # Download backup from S3
        with tempfile.NamedTemporaryFile() as temp_file:
            s3_client.download_fileobj(bucket, backup_key, temp_file)
            temp_file.seek(0)
            
            # Upload to Glacier
            response = glacier_client.upload_archive(
                vaultName=glacier_vault,
                archiveDescription=f'Archived backup: {backup_key}',
                body=temp_file
            )
            
            archive_id = response['archiveId']
            
            # Store archive metadata
            metadata = {
                'original_key': backup_key,
                'archive_id': archive_id,
                'archived_date': datetime.now().isoformat(),
                'original_size': backup_info['size']
            }
            
            metadata_key = f"archived/{backup_key}.metadata.json"
            s3_client.put_object(
                Bucket=bucket,
                Key=metadata_key,
                Body=json.dumps(metadata, indent=2),
                ContentType='application/json',
                ServerSideEncryption='AES256'
            )
            
            # Remove original backup from S3
            s3_client.delete_object(Bucket=bucket, Key=backup_key)
            
            logger.info(f"Successfully archived {backup_key} to Glacier: {archive_id}")
            
            return {
                'repository': backup_info.get('repository_name', 'unknown'),
                'backup_key': backup_key,
                'backup_filename': backup_info.get('backup_filename', ''),
                'archive_id': archive_id,
                'size_bytes': backup_info.get('size', 0),
                'age_days': backup_info.get('age_days', 0),
                'success': True
            }
    
    except Exception as e:
        logger.error(f"Failed to archive {backup_key}: {str(e)}")
        return {
            'repository': backup_info.get('repository_name', 'unknown'),
            'backup_key': backup_key,
            'backup_filename': backup_info.get('backup_filename', ''),
            'success': False,
            'error': str(e)
        }

def create_monthly_archive(bucket: str, glacier_vault: str, archive_date: str) -> Dict[str, Any]:
    """
    Create a monthly archive from all nightly backups in the specified month.
    """
    s3_client = boto3.client('s3')
    glacier_client = boto3.client('glacier')
    
    # List all nightly backup dates for the month
    prefix = f"nightly/{archive_date}"
    backup_dates = get_backup_dates_for_month(s3_client, bucket, prefix)
    
    if not backup_dates:
        logger.warning(f"No backups found for month {archive_date}")
        return {'status': 'skipped', 'reason': 'no_backups_found'}
    
    with tempfile.TemporaryDirectory() as temp_dir:
        archive_path = os.path.join(temp_dir, f"full-backup-{archive_date}.tar.gz")
        
        # Download and combine all nightly backups
        download_and_combine_backups(s3_client, bucket, backup_dates, temp_dir)
        
        # Create combined archive
        create_combined_archive(temp_dir, archive_path, archive_date)
        
        # Upload to Glacier
        archive_id = upload_to_glacier(glacier_client, glacier_vault, archive_path, archive_date)
        
        # Store archive metadata in S3
        store_archive_metadata(s3_client, bucket, archive_date, archive_id, archive_path)
        
        file_size = os.path.getsize(archive_path)
        
        return {
            'status': 'completed',
            'archive_id': archive_id,
            'size_bytes': file_size,
            'backup_dates': backup_dates
        }

def get_backup_dates_for_month(s3_client, bucket: str, prefix: str) -> List[str]:
    """
    Get all backup dates for a specific month.
    """
    backup_dates = []
    
    try:
        paginator = s3_client.get_paginator('list_objects_v2')
        pages = paginator.paginate(Bucket=bucket, Prefix=prefix, Delimiter='/')
        
        for page in pages:
            for prefix_info in page.get('CommonPrefixes', []):
                date_prefix = prefix_info['Prefix']
                # Extract date from prefix like "nightly/2023-11-15/"
                date_part = date_prefix.split('/')[-2]
                if date_part and date_part != prefix.split('/')[-1]:
                    backup_dates.append(date_part)
    
    except Exception as e:
        logger.error(f"Error listing backup dates: {str(e)}")
    
    return sorted(backup_dates)

def download_and_combine_backups(s3_client, bucket: str, backup_dates: List[str], temp_dir: str) -> None:
    """
    Download all backup files for the specified dates.
    """
    for date in backup_dates:
        date_dir = os.path.join(temp_dir, date)
        os.makedirs(date_dir, exist_ok=True)
        
        # List all backup files for this date
        prefix = f"nightly/{date}/"
        
        try:
            paginator = s3_client.get_paginator('list_objects_v2')
            pages = paginator.paginate(Bucket=bucket, Prefix=prefix)
            
            for page in pages:
                for obj in page.get('Contents', []):
                    key = obj['Key']
                    if key.endswith('.tar.gz'):
                        filename = os.path.basename(key)
                        local_path = os.path.join(date_dir, filename)
                        
                        logger.info(f"Downloading {key}")
                        s3_client.download_file(bucket, key, local_path)
        
        except Exception as e:
            logger.error(f"Error downloading backups for {date}: {str(e)}")

def create_combined_archive(temp_dir: str, archive_path: str, archive_date: str) -> None:
    """
    Create a combined archive from all downloaded backup files.
    """
    with tarfile.open(archive_path, 'w:gz') as tar:
        for root, dirs, files in os.walk(temp_dir):
            if root == temp_dir:
                continue
            
            for file in files:
                file_path = os.path.join(root, file)
                # Create archive name that includes the date structure
                arcname = os.path.relpath(file_path, temp_dir)
                tar.add(file_path, arcname=arcname)

def upload_to_glacier(glacier_client, vault_name: str, archive_path: str, archive_date: str) -> str:
    """
    Upload archive to AWS Glacier.
    """
    with open(archive_path, 'rb') as f:
        response = glacier_client.upload_archive(
            vaultName=vault_name,
            archiveDescription=f'Monthly backup archive for {archive_date}',
            body=f
        )
    
    archive_id = response['archiveId']
    logger.info(f"Uploaded to Glacier with archive ID: {archive_id}")
    
    return archive_id

def store_archive_metadata(s3_client, bucket: str, archive_date: str, archive_id: str, archive_path: str) -> None:
    """
    Store archive metadata in S3 for future reference.
    """
    metadata = {
        'archive_date': archive_date,
        'archive_id': archive_id,
        'timestamp': datetime.now().isoformat(),
        'size_bytes': os.path.getsize(archive_path),
        'description': f'Monthly backup archive for {archive_date}'
    }
    
    key = f"monthly-archives/{archive_date}/metadata.json"
    
    s3_client.put_object(
        Bucket=bucket,
        Key=key,
        Body=json.dumps(metadata, indent=2),
        ContentType='application/json',
        ServerSideEncryption='AES256'
    )

def cleanup_old_backups(bucket: str, retention_days: int) -> Dict[str, Any]:
    """
    Clean up nightly backups older than the retention period.
    """
    s3_client = boto3.client('s3')
    cutoff_date = datetime.now() - timedelta(days=retention_days)
    
    deleted_objects = []
    
    try:
        paginator = s3_client.get_paginator('list_objects_v2')
        pages = paginator.paginate(Bucket=bucket, Prefix='nightly/')
        
        for page in pages:
            for obj in page.get('Contents', []):
                # Parse date from object key
                key_parts = obj['Key'].split('/')
                if len(key_parts) >= 2:
                    try:
                        backup_date = datetime.strptime(key_parts[1], '%Y-%m-%d')
                        if backup_date < cutoff_date:
                            s3_client.delete_object(Bucket=bucket, Key=obj['Key'])
                            deleted_objects.append(obj['Key'])
                            logger.info(f"Deleted old backup: {obj['Key']}")
                    except ValueError:
                        continue
    
    except Exception as e:
        logger.error(f"Error during cleanup: {str(e)}")
        return {'status': 'error', 'error': str(e)}
    
    return {
        'status': 'completed',
        'deleted_count': len(deleted_objects),
        'retention_days': retention_days
    }

def send_notification(results: List[Dict[str, Any]], job_type: str) -> None:
    """
    Send email notification about backup/archival job completion.
    """
    try:
        sns_client = boto3.client('sns')
        topic_arn = os.environ.get('SNS_TOPIC_ARN')
        
        if not topic_arn:
            logger.warning("SNS_TOPIC_ARN not set, skipping notification")
            return
        
        # Calculate statistics for archival
        total_items = len(results) if isinstance(results, list) else 1
        successful = 1 if isinstance(results, dict) and results.get('status') == 'completed' else 0
        failed = total_items - successful
        
        # Create subject
        status = "SUCCESS" if failed == 0 else "FAILED"
        subject = f"GitHub Backup {job_type.title()} - {status}"
        
        # Create formatted message
        message = create_email_message(job_type, results)
        
        # Send notification
        sns_client.publish(
            TopicArn=topic_arn,
            Subject=subject,
            Message=message
        )
        
        logger.info(f"Notification sent: {subject}")
        
    except Exception as e:
        logger.error(f"Failed to send notification: {str(e)}")

def create_email_message(job_type: str, results) -> str:
    """
    Create a nicely formatted email message for archival jobs.
    """
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')
    
    message = f"""GitHub Backup {job_type.title()} Report
========================================

Execution Time: {timestamp}
"""
    
    if isinstance(results, dict):
        if results.get('status') == 'completed':
            message += f"Status: SUCCESS\n"
            if 'archive_id' in results:
                message += f"Archive ID: {results['archive_id']}\n"
            if 'archive_size' in results:
                size_mb = results['archive_size'] / (1024 * 1024)
                message += f"Archive Size: {size_mb:.2f} MB\n"
            if 'deleted_count' in results:
                message += f"Old Backups Cleaned: {results['deleted_count']}\n"
        else:
            message += f"Status: FAILED\n"
            if 'error' in results:
                message += f"Error: {results['error']}\n"
    
    message += f"\nFor complete logs, check CloudWatch: /aws/lambda/github-backup-{job_type.replace(' ', '-')}\n"
    
    return message
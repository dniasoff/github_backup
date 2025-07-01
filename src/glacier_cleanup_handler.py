import json
import logging
import os
from datetime import datetime, timedelta
from typing import Dict, List, Any
import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def lambda_handler(event: Dict[str, Any], context) -> Dict[str, Any]:
    """
    Lambda function to clean up Glacier archives older than 2 years.
    Runs monthly to check for archives that have exceeded the 2-year retention period.
    """
    try:
        glacier_vault = os.environ['GLACIER_VAULT_NAME']
        retention_years = int(os.environ.get('GLACIER_RETENTION_YEARS', '2'))
        
        # Calculate cutoff date (2 years ago)
        cutoff_date = datetime.now() - timedelta(days=365 * retention_years)
        
        logger.info(f"Starting Glacier cleanup for archives older than {cutoff_date.isoformat()}")
        
        # Get Glacier inventory and clean up old archives
        cleanup_result = cleanup_old_glacier_archives(glacier_vault, cutoff_date)
        
        logger.info(f"Glacier cleanup completed")
        
        # Send notification
        send_cleanup_notification(cleanup_result, retention_years)
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Glacier cleanup completed successfully',
                'cutoff_date': cutoff_date.isoformat(),
                'cleanup_result': cleanup_result
            })
        }
        
    except Exception as e:
        logger.error(f"Error during Glacier cleanup: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': f'Glacier cleanup failed: {str(e)}'
            })
        }

def cleanup_old_glacier_archives(vault_name: str, cutoff_date: datetime) -> Dict[str, Any]:
    """
    Clean up Glacier archives older than the cutoff date.
    """
    glacier_client = boto3.client('glacier')
    s3_client = boto3.client('s3')
    
    # Get S3 bucket name for metadata lookup
    s3_bucket = os.environ['S3_BUCKET_NAME']
    
    deleted_archives = []
    errors = []
    
    try:
        # List archived metadata from S3 to find archives older than cutoff
        paginator = s3_client.get_paginator('list_objects_v2')
        pages = paginator.paginate(Bucket=s3_bucket, Prefix='archived/')
        
        for page in pages:
            for obj in page.get('Contents', []):
                if obj['Key'].endswith('.metadata.json'):
                    try:
                        # Get metadata
                        response = s3_client.get_object(Bucket=s3_bucket, Key=obj['Key'])
                        metadata = json.loads(response['Body'].read())
                        
                        # Parse archive date
                        archived_date_str = metadata.get('archived_date')
                        if archived_date_str:
                            archived_date = datetime.fromisoformat(archived_date_str.replace('Z', '+00:00'))
                            
                            # Check if archive is older than cutoff (2 years)
                            if archived_date.replace(tzinfo=None) < cutoff_date:
                                archive_id = metadata.get('archive_id')
                                original_key = metadata.get('original_key', 'unknown')
                                
                                if archive_id:
                                    # Delete from Glacier
                                    try:
                                        glacier_client.delete_archive(
                                            vaultName=vault_name,
                                            archiveId=archive_id
                                        )
                                        
                                        # Delete metadata from S3
                                        s3_client.delete_object(Bucket=s3_bucket, Key=obj['Key'])
                                        
                                        deleted_archives.append({
                                            'archive_id': archive_id,
                                            'original_key': original_key,
                                            'archived_date': archived_date_str,
                                            'metadata_key': obj['Key']
                                        })
                                        
                                        logger.info(f"Deleted Glacier archive: {original_key} (archived: {archived_date_str})")
                                        
                                    except Exception as e:
                                        error_msg = f"Failed to delete archive {archive_id}: {str(e)}"
                                        logger.error(error_msg)
                                        errors.append(error_msg)
                    
                    except Exception as e:
                        error_msg = f"Failed to process metadata {obj['Key']}: {str(e)}"
                        logger.error(error_msg)
                        errors.append(error_msg)
    
    except Exception as e:
        error_msg = f"Failed to list archived metadata: {str(e)}"
        logger.error(error_msg)
        errors.append(error_msg)
    
    return {
        'deleted_count': len(deleted_archives),
        'deleted_archives': deleted_archives,
        'errors': errors,
        'cutoff_date': cutoff_date.isoformat()
    }

def send_cleanup_notification(cleanup_result: Dict[str, Any], retention_years: int) -> None:
    """
    Send notification about Glacier cleanup results.
    """
    try:
        sns_client = boto3.client('sns')
        topic_arn = os.environ.get('SNS_TOPIC_ARN')
        
        if not topic_arn:
            logger.warning("SNS_TOPIC_ARN not set, skipping notification")
            return
        
        deleted_count = cleanup_result.get('deleted_count', 0)
        errors = cleanup_result.get('errors', [])
        cutoff_date = cleanup_result.get('cutoff_date', 'unknown')
        
        # Create subject
        status = "SUCCESS" if len(errors) == 0 else "PARTIAL SUCCESS" if deleted_count > 0 else "FAILED"
        subject = f"Glacier Cleanup ({retention_years}yr retention) - {status} ({deleted_count} deleted)"
        
        # Create message
        message = f"""Glacier Archive Cleanup Report
========================================

Execution Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}
Retention Policy: {retention_years} years
Cutoff Date: {cutoff_date}
Archives Deleted: {deleted_count}
Errors: {len(errors)}

"""
        
        if deleted_count > 0:
            message += "DELETED ARCHIVES:\n"
            message += "----------------\n"
            for archive in cleanup_result.get('deleted_archives', [])[:20]:  # Show first 20
                message += f"• {archive.get('original_key', 'unknown')} (archived: {archive.get('archived_date', 'unknown')})\n"
            
            if deleted_count > 20:
                message += f"... and {deleted_count - 20} more archives\n"
            message += "\n"
        
        if errors:
            message += "ERRORS:\n"
            message += "-------\n"
            for error in errors[:10]:  # Show first 10 errors
                message += f"• {error}\n"
            
            if len(errors) > 10:
                message += f"... and {len(errors) - 10} more errors\n"
        
        message += f"\nFor complete logs, check CloudWatch: /aws/lambda/github-backup-glacier-cleanup\n"
        
        # Send notification
        sns_client.publish(
            TopicArn=topic_arn,
            Subject=subject,
            Message=message
        )
        
        logger.info(f"Cleanup notification sent: {subject}")
        
    except Exception as e:
        logger.error(f"Failed to send cleanup notification: {str(e)}")
import json
import logging
import os
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
from decimal import Decimal
import boto3
from botocore.exceptions import ClientError
from audit_logger import audit_logger
from auth_handler import validate_token_for_api

logger = logging.getLogger()
logger.setLevel(logging.INFO)

class DecimalEncoder(json.JSONEncoder):
    """Custom JSON encoder that handles DynamoDB Decimal objects."""
    def default(self, o):
        if isinstance(o, Decimal):
            # Convert Decimal to int if it's a whole number, otherwise float
            if o % 1 == 0:
                return int(o)
            else:
                return float(o)
        return super(DecimalEncoder, self).default(o)

def json_dumps(obj):
    """JSON dumps with custom Decimal encoder."""
    return json.dumps(obj, cls=DecimalEncoder)

def lambda_handler(event: Dict[str, Any], context) -> Dict[str, Any]:
    """
    API Gateway Lambda handler for backup management interface.
    Provides REST endpoints for viewing history and managing downloads.
    """
    try:
        # Parse API Gateway event
        http_method = event.get('httpMethod', '')
        resource_path = event.get('resource', '')
        path_parameters = event.get('pathParameters', {}) or {}
        query_parameters = event.get('queryStringParameters', {}) or {}
        body = event.get('body', '')
        headers = event.get('headers', {})
        
        logger.info(f"API request: {http_method} {resource_path}")
        
        # Check authentication for all endpoints
        auth_result = check_authentication(headers)
        if auth_result['statusCode'] != 200:
            return auth_result
        
        user_info = json.loads(auth_result['body'])
        username = user_info.get('username', 'unknown')
        
        # Route to appropriate handler
        if resource_path == '/repositories' and http_method == 'GET':
            return get_repositories_list(query_parameters)
        
        elif resource_path == '/repositories/{repository}/history' and http_method == 'GET':
            repository_name = path_parameters.get('repository')
            return get_repository_history(repository_name, query_parameters)
        
        elif resource_path == '/repositories/{repository}/versions' and http_method == 'GET':
            repository_name = path_parameters.get('repository')
            return get_repository_versions(repository_name, query_parameters)
        
        elif resource_path == '/repositories/{repository}/downloads' and http_method == 'GET':
            repository_name = path_parameters.get('repository')
            return get_repository_downloads(repository_name, query_parameters)
        
        elif resource_path == '/events' and http_method == 'GET':
            return get_recent_events(query_parameters)
        
        elif resource_path == '/download' and http_method == 'POST':
            request_data = json.loads(body) if body else {}
            request_data['user_id'] = username  # Add authenticated user
            return initiate_download(request_data)
        
        elif resource_path == '/download/{download_id}' and http_method == 'GET':
            download_id = path_parameters.get('download_id')
            return get_download_status(download_id)
        
        elif resource_path == '/dashboard' and http_method == 'GET':
            return get_dashboard_data()
        
        else:
            return {
                'statusCode': 404,
                'headers': {'Content-Type': 'application/json'},
                'body': json_dumps({'error': 'Endpoint not found'})
            }
            
    except Exception as e:
        logger.error(f"API error: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json_dumps({'error': f'Internal server error: {str(e)}'})
        }

def check_authentication(headers: Dict[str, str]) -> Dict[str, Any]:
    """Check if the request has valid authentication."""
    try:
        auth_header = headers.get('Authorization', headers.get('authorization', ''))
        
        if not auth_header.startswith('Bearer '):
            return {
                'statusCode': 401,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json_dumps({'error': 'Missing or invalid authorization header'})
            }
        
        token = auth_header[7:]  # Remove 'Bearer ' prefix
        payload = validate_token_for_api(token)
        
        if not payload:
            return {
                'statusCode': 401,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json_dumps({'error': 'Invalid or expired token'})
            }
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json_dumps({
                'username': payload.get('sub'),
                'expires_at': datetime.fromtimestamp(payload.get('exp'), timezone.utc).isoformat() if payload.get('exp') else None
            })
        }
        
    except Exception as e:
        logger.error(f"Authentication check error: {str(e)}")
        return {
            'statusCode': 401,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json_dumps({'error': 'Authentication failed'})
        }

def get_repositories_list(query_params: Dict[str, str]) -> Dict[str, Any]:
    """Get list of repositories with their latest backup information (optimized)."""
    try:
        # Get pagination parameters
        limit = min(int(query_params.get('limit', '50')), 500)  # Max 500 per page to show all repos
        last_key = query_params.get('last_key')
        include_versions = query_params.get('include_versions', 'false').lower() == 'true'
        
        dynamodb = boto3.resource('dynamodb')
        history_table = dynamodb.Table('github-backup-repository-history')
        
        # Get unique repository names efficiently (faster than full scan)
        scan_kwargs = {
            'ProjectionExpression': 'repository_name',
            'Select': 'SPECIFIC_ATTRIBUTES'
        }
        
        if last_key:
            scan_kwargs['ExclusiveStartKey'] = {'repository_name': last_key}
        
        # Get all unique repository names efficiently
        repo_names = set()
        
        # Scan all items to get complete repository list
        while True:
            response = history_table.scan(**scan_kwargs)
            
            for item in response.get('Items', []):
                repo_names.add(item['repository_name'])
            
            # Check if there's more data to scan
            if 'LastEvaluatedKey' not in response:
                break
                
            # Set up for next scan page
            scan_kwargs['ExclusiveStartKey'] = response['LastEvaluatedKey']
        
        logger.info(f"Found {len(repo_names)} unique repositories in DynamoDB")
        
        # Apply pagination to the sorted list of unique names
        sorted_repo_names = sorted(repo_names)
        
        # Handle pagination
        start_index = 0
        if last_key:
            try:
                start_index = sorted_repo_names.index(last_key) + 1
            except ValueError:
                start_index = 0
        
        # Get the page of repositories
        page_repo_names = sorted_repo_names[start_index:start_index + limit]
        
        # Get latest backup for each repository using efficient queries
        repositories = []
        for repo_name in page_repo_names:
            try:
                # Query for latest backup only (much faster than getting all versions)
                latest_response = history_table.query(
                    KeyConditionExpression=boto3.dynamodb.conditions.Key('repository_name').eq(repo_name),
                    ScanIndexForward=False,  # Newest first
                    Limit=1
                )
                
                if latest_response['Items']:
                    latest_backup = latest_response['Items'][0]
                    
                    # Get backup count efficiently
                    count_response = history_table.query(
                        KeyConditionExpression=boto3.dynamodb.conditions.Key('repository_name').eq(repo_name),
                        Select='COUNT'
                    )
                    backup_count = count_response['Count']
                    
                    repo_data = {
                        'name': repo_name,
                        'latest_backup': latest_backup,
                        'backup_count': backup_count,
                        'total_size': latest_backup.get('size_bytes', 0) * backup_count  # Estimate
                    }
                    
                    # Only include all versions if specifically requested
                    if include_versions:
                        versions_response = history_table.query(
                            KeyConditionExpression=boto3.dynamodb.conditions.Key('repository_name').eq(repo_name),
                            ScanIndexForward=False,  # Newest first
                            Limit=10  # Limit to last 10 versions for performance
                        )
                        repo_data['backup_versions'] = versions_response['Items']
                    
                    repositories.append(repo_data)
                    
            except Exception as e:
                logger.warning(f"Error getting data for repository {repo_name}: {str(e)}")
                continue
        
        # Sort by latest backup date
        repositories.sort(key=lambda x: x['latest_backup']['backup_version'], reverse=True)
        
        # Determine next page key
        next_key = None
        if start_index + limit < len(sorted_repo_names):
            next_key = page_repo_names[-1] if page_repo_names else None
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
                'Cache-Control': 'max-age=60'  # Cache for 1 minute
            },
            'body': json_dumps({
                'repositories': repositories,
                'total_count': len(repositories),
                'next_key': next_key,
                'has_more': next_key is not None
            })
        }
        
    except Exception as e:
        logger.error(f"Error getting repositories list: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json_dumps({'error': str(e)})
        }

def get_repository_history(repository_name: str, query_params: Dict[str, str]) -> Dict[str, Any]:
    """Get backup history for a specific repository."""
    try:
        if not repository_name:
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json'},
                'body': json_dumps({'error': 'Repository name is required'})
            }
        
        limit = int(query_params.get('limit', '50'))
        
        # Get repository history from audit logger
        history = audit_logger.get_repository_history(repository_name, limit)
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
                'Cache-Control': 'max-age=300'  # Cache for 5 minutes
            },
            'body': json_dumps({
                'repository_name': repository_name,
                'history': history,
                'count': len(history)
            })
        }
        
    except Exception as e:
        logger.error(f"Error getting repository history: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json_dumps({'error': str(e)})
        }

def get_repository_versions(repository_name: str, query_params: Dict[str, str]) -> Dict[str, Any]:
    """Get backup versions for a specific repository (optimized for UI)."""
    try:
        if not repository_name:
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json'},
                'body': json_dumps({'error': 'Repository name is required'})
            }
        
        limit = min(int(query_params.get('limit', '20')), 50)  # Max 50 versions
        last_key = query_params.get('last_key')
        
        dynamodb = boto3.resource('dynamodb')
        history_table = dynamodb.Table('github-backup-repository-history')
        
        # Build query parameters
        query_kwargs = {
            'KeyConditionExpression': boto3.dynamodb.conditions.Key('repository_name').eq(repository_name),
            'ScanIndexForward': False,  # Newest first
            'Limit': limit
        }
        
        if last_key:
            query_kwargs['ExclusiveStartKey'] = {
                'repository_name': repository_name,
                'backup_version': last_key
            }
        
        # Query for backup versions efficiently
        response = history_table.query(**query_kwargs)
        versions = response.get('Items', [])
        
        # Calculate total size
        total_size = sum(version.get('size_bytes', 0) for version in versions)
        
        # Determine next page key
        next_key = None
        if response.get('LastEvaluatedKey'):
            next_key = response['LastEvaluatedKey']['backup_version']
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
                'Cache-Control': 'max-age=60'  # Cache for 1 minute
            },
            'body': json_dumps({
                'repository_name': repository_name,
                'backup_versions': versions,
                'count': len(versions),
                'total_size': total_size,
                'next_key': next_key,
                'has_more': next_key is not None
            })
        }
        
    except Exception as e:
        logger.error(f"Error getting repository versions: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json_dumps({'error': str(e)})
        }

def get_recent_events(query_params: Dict[str, str]) -> Dict[str, Any]:
    """Get recent audit events."""
    try:
        hours = int(query_params.get('hours', '24'))
        limit = int(query_params.get('limit', '100'))
        
        events = audit_logger.get_recent_events(hours, limit)
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json_dumps({
                'events': events,
                'count': len(events),
                'hours': hours
            })
        }
        
    except Exception as e:
        logger.error(f"Error getting recent events: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json_dumps({'error': str(e)})
        }

def initiate_download(request_body: Dict[str, Any]) -> Dict[str, Any]:
    """Initiate a backup download operation."""
    try:
        repository_name = request_body.get('repository_name')
        backup_version = request_body.get('backup_version')
        user_id = request_body.get('user_id', 'unknown')  # Set by authentication middleware
        
        if not repository_name or not backup_version:
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json'},
                'body': json_dumps({'error': 'repository_name and backup_version are required'})
            }
        
        # Get backup details from repository history
        dynamodb = boto3.resource('dynamodb')
        history_table = dynamodb.Table('github-backup-repository-history')
        
        response = history_table.get_item(
            Key={
                'repository_name': repository_name,
                'backup_version': backup_version
            }
        )
        
        if 'Item' not in response:
            return {
                'statusCode': 404,
                'headers': {'Content-Type': 'application/json'},
                'body': json_dumps({'error': 'Backup not found'})
            }
        
        backup_item = response['Item']
        storage_class = backup_item.get('storage_class', 's3')
        s3_key = backup_item.get('s3_key', '')
        
        # Determine download type based on storage class
        if storage_class == 's3':
            download_type = 's3_direct'
            source_location = s3_key
        else:
            download_type = 'glacier_retrieval'
            source_location = backup_item.get('archive_id', s3_key)
        
        # Create download operation
        download_id = audit_logger.create_download_operation(
            repository_name=repository_name,
            backup_version=backup_version,
            user_id=user_id,
            download_type=download_type,
            source_location=source_location
        )
        
        if not download_id:
            return {
                'statusCode': 500,
                'headers': {'Content-Type': 'application/json'},
                'body': json_dumps({'error': 'Failed to create download operation'})
            }
        
        # Handle download based on type
        if download_type == 's3_direct':
            # Generate pre-signed URL for S3 download
            result = handle_s3_download(download_id, s3_key)
        else:
            # Initiate Glacier retrieval
            result = handle_glacier_download(download_id, source_location, repository_name)
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json_dumps({
                'download_id': download_id,
                'download_type': download_type,
                'status': result.get('status', 'requested'),
                'details': result
            })
        }
        
    except Exception as e:
        logger.error(f"Error initiating download: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json_dumps({'error': str(e)})
        }

def handle_s3_download(download_id: str, s3_key: str) -> Dict[str, Any]:
    """Handle S3 backup download by generating pre-signed URL."""
    try:
        s3_client = boto3.client('s3')
        bucket_name = os.environ['S3_BUCKET_NAME']
        
        # Extract repository name from S3 key for filename
        # S3 key format: nightly/DevToolStack/2025-07-01-22-32.tar.gz
        # Extract: DevToolStack
        if '/' in s3_key:
            parts = s3_key.split('/')
            if len(parts) >= 2:
                repository_name = parts[1] if parts[0] in ['nightly', 'final'] else parts[0]
                filename = f"{repository_name}.tar.gz"
            else:
                filename = s3_key.split('/')[-1]  # fallback to original filename
        else:
            filename = s3_key  # fallback to S3 key as filename
        
        # Generate pre-signed URL valid for 24 hours with proper filename
        download_url = s3_client.generate_presigned_url(
            'get_object',
            Params={
                'Bucket': bucket_name, 
                'Key': s3_key,
                'ResponseContentDisposition': f'attachment; filename="{filename}"'
            },
            ExpiresIn=86400  # 24 hours
        )
        
        # Update download operation status
        audit_logger.update_download_status(
            download_id=download_id,
            status='completed',
            details={
                'download_url': download_url,
                'expires_at': (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat()
            }
        )
        
        return {
            'status': 'completed',
            'download_url': download_url,
            'expires_in_hours': 24
        }
        
    except Exception as e:
        audit_logger.update_download_status(
            download_id=download_id,
            status='failed',
            error=str(e)
        )
        raise e

def handle_glacier_download(download_id: str, archive_id: str, repository_name: str) -> Dict[str, Any]:
    """Handle S3 Glacier storage class download by initiating restore request."""
    try:
        s3_client = boto3.client('s3')
        bucket_name = os.environ['S3_BUCKET_NAME']
        
        # archive_id is actually the S3 key for S3 Glacier storage class
        s3_key = archive_id
        
        # Check if object is already being restored or is restored
        try:
            response = s3_client.head_object(Bucket=bucket_name, Key=s3_key)
            
            # Check restore status
            if 'Restore' in response:
                restore_status = response['Restore']
                if 'ongoing-request="true"' in restore_status:
                    # Restore is already in progress
                    audit_logger.update_download_status(
                        download_id=download_id,
                        status='in_progress',
                        details={
                            'restore_status': 'already_in_progress',
                            'estimated_completion': '3-5 hours'
                        }
                    )
                    return {
                        'status': 'in_progress',
                        'restore_status': 'already_in_progress',
                        'estimated_completion': '3-5 hours'
                    }
                elif 'ongoing-request="false"' in restore_status:
                    # Object is already restored, can download directly
                    return handle_s3_download(download_id, s3_key)
            
            # Object needs to be restored
            restore_request = {
                'Days': 7,  # Keep restored copy for 7 days
                'GlacierJobParameters': {
                    'Tier': 'Standard'  # Standard: 3-5 hours
                }
            }
            
            # Support different retrieval speeds if requested
            retrieval_tier = request_body.get('retrieval_tier', 'Standard') if 'request_body' in locals() else 'Standard'
            if retrieval_tier in ['Expedited', 'Standard', 'Bulk']:
                restore_request['GlacierJobParameters']['Tier'] = retrieval_tier
            
            # Initiate restore
            s3_client.restore_object(
                Bucket=bucket_name,
                Key=s3_key,
                RestoreRequest=restore_request
            )
            
            # Map tier to estimated completion time
            completion_times = {
                'Expedited': '1-5 minutes',
                'Standard': '3-5 hours',
                'Bulk': '5-12 hours'
            }
            estimated_time = completion_times.get(retrieval_tier, '3-5 hours')
            
            # Update download operation status
            audit_logger.update_download_status(
                download_id=download_id,
                status='in_progress',
                details={
                    's3_key': s3_key,
                    'restore_tier': retrieval_tier,
                    'estimated_completion': estimated_time,
                    'restore_days': 7
                }
            )
            
            # Log the restoration event
            audit_logger.log_backup_event(
                repository_name=repository_name,
                event_type='glacier_restore_initiated',
                status='started',
                details={
                    's3_key': s3_key,
                    'tier': retrieval_tier,
                    'download_id': download_id
                }
            )
            
            return {
                'status': 'in_progress',
                'restore_tier': retrieval_tier,
                'estimated_completion': estimated_time
            }
            
        except ClientError as e:
            if e.response['Error']['Code'] == 'NotFound':
                raise Exception(f"Object not found: {s3_key}")
            raise e
            
    except Exception as e:
        audit_logger.update_download_status(
            download_id=download_id,
            status='failed',
            error=str(e)
        )
        raise e

def get_download_status(download_id: str) -> Dict[str, Any]:
    """Get status of a download operation."""
    try:
        if not download_id:
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json'},
                'body': json_dumps({'error': 'Download ID is required'})
            }
        
        dynamodb = boto3.resource('dynamodb')
        download_table = dynamodb.Table('github-backup-download-operations')
        
        response = download_table.get_item(Key={'download_id': download_id})
        
        if 'Item' not in response:
            return {
                'statusCode': 404,
                'headers': {'Content-Type': 'application/json'},
                'body': json_dumps({'error': 'Download operation not found'})
            }
        
        download_item = response['Item']
        
        # If it's a Glacier download, check job status
        if download_item.get('download_type') == 'glacier_retrieval' and download_item.get('status') == 'in_progress':
            glacier_job_id = download_item.get('details', {}).get('glacier_job_id')
            if glacier_job_id:
                updated_status = check_glacier_job_status(glacier_job_id, download_id)
                download_item.update(updated_status)
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json_dumps(download_item)
        }
        
    except Exception as e:
        logger.error(f"Error getting download status: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json_dumps({'error': str(e)})
        }

def check_glacier_job_status(job_id: str, download_id: str) -> Dict[str, Any]:
    """Check S3 Glacier restore status and update if completed."""
    try:
        # Get download details to find S3 key
        dynamodb = boto3.resource('dynamodb')
        download_table = dynamodb.Table('github-backup-download-operations')
        
        response = download_table.get_item(Key={'download_id': download_id})
        if 'Item' not in response:
            return {'status': 'failed', 'error': 'Download operation not found'}
            
        download_item = response['Item']
        s3_key = download_item.get('details', {}).get('s3_key') or download_item.get('source_location')
        
        if not s3_key:
            return {'status': 'failed', 'error': 'S3 key not found in download details'}
        
        # Check S3 object restore status
        s3_client = boto3.client('s3')
        bucket_name = os.environ['S3_BUCKET_NAME']
        
        try:
            response = s3_client.head_object(Bucket=bucket_name, Key=s3_key)
            
            if 'Restore' in response:
                restore_status = response['Restore']
                
                if 'ongoing-request="false"' in restore_status:
                    # Restore completed, generate download URL
                    download_url = s3_client.generate_presigned_url(
                        'get_object',
                        Params={
                            'Bucket': bucket_name,
                            'Key': s3_key,
                            'ResponseContentDisposition': f'attachment; filename="{s3_key.split("/")[-1]}"'
                        },
                        ExpiresIn=86400  # 24 hours
                    )
                    
                    audit_logger.update_download_status(
                        download_id=download_id,
                        status='completed',
                        details={
                            'restore_completed': True,
                            'completed_at': datetime.now(timezone.utc).isoformat(),
                            'download_url': download_url,
                            'expires_at': (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat()
                        }
                    )
                    
                    return {
                        'status': 'completed',
                        'download_url': download_url,
                        'expires_in_hours': 24
                    }
                    
                elif 'ongoing-request="true"' in restore_status:
                    # Still in progress
                    return {'status': 'in_progress'}
            else:
                # No restore info, object might be in STANDARD storage or restore not initiated
                return {'status': 'failed', 'error': 'No restore information found'}
                
        except ClientError as e:
            if e.response['Error']['Code'] == 'NotFound':
                return {'status': 'failed', 'error': 'Object not found'}
            raise e
            
    except Exception as e:
        logger.error(f"Error checking S3 Glacier restore status: {str(e)}")
        return {'status': 'in_progress'}

def get_repository_downloads(repository_name: str, query_params: Dict[str, str]) -> Dict[str, Any]:
    """Get download operations for a specific repository."""
    try:
        if not repository_name:
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json'},
                'body': json_dumps({'error': 'Repository name is required'})
            }
        
        # Query download operations table
        dynamodb = boto3.resource('dynamodb')
        downloads_table = dynamodb.Table('github-backup-download-operations')
        
        # Query by repository name using the RepositoryIndex GSI
        response = downloads_table.query(
            IndexName='RepositoryIndex',
            KeyConditionExpression=boto3.dynamodb.conditions.Key('repository_name').eq(repository_name),
            ScanIndexForward=False,  # Sort by download_id descending (newest first)
            Limit=50  # Limit to last 50 downloads
        )
        
        downloads = []
        for item in response.get('Items', []):
            # Convert DynamoDB item to API response format
            download = {
                'id': item.get('download_id'),
                'download_id': item.get('download_id'),
                'repository_name': item.get('repository_name'),
                'backup_version': item.get('backup_version'),
                'download_type': item.get('download_type', 's3_direct'),
                'status': item.get('status', 'unknown'),
                'created_at': item.get('created_at'),
                'user_id': item.get('user_id'),
                'details': item.get('details', {})
            }
            
            # Add error if present
            if 'error' in item:
                download['error'] = item['error']
            
            downloads.append(download)
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json_dumps({
                'repository_name': repository_name,
                'downloads': downloads,
                'count': len(downloads)
            })
        }
        
    except Exception as e:
        logger.error(f"Error getting repository downloads for {repository_name}: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json_dumps({'error': f'Failed to get downloads: {str(e)}'})
        }

def get_dashboard_data() -> Dict[str, Any]:
    """Get dashboard statistics and summary data (optimized)."""
    try:
        # Get recent events for stats (increased limit to capture all backup events)
        recent_events = audit_logger.get_recent_events(hours=24, limit=1500)
        
        # Calculate statistics
        backup_events = [e for e in recent_events if e.get('event_type') == 'backup']
        successful_backups = [e for e in backup_events if e.get('status') == 'completed']
        failed_backups = [e for e in backup_events if e.get('status') == 'failed']
        started_backups = [e for e in backup_events if e.get('status') == 'started']
        in_progress_backups = [e for e in backup_events if e.get('status') == 'in_progress']
        
        # All backup events (including started/in-progress for total activity)
        total_backup_events = backup_events
        # Final status events for success rate calculation
        final_backup_events = successful_backups + failed_backups
        
        # Get total repository count efficiently (estimate from recent data)
        unique_repos = set()
        for event in backup_events:
            if 'repository_name' in event:
                unique_repos.add(event['repository_name'])
        
        # Always do a complete scan for accurate count (recent events may not capture all repos)
        if True:
            try:
                dynamodb = boto3.resource('dynamodb')
                history_table = dynamodb.Table('github-backup-repository-history')
                
                # Scan all items to get accurate repository count
                scan_kwargs = {
                    'ProjectionExpression': 'repository_name',
                    'Select': 'SPECIFIC_ATTRIBUTES'
                }
                
                while True:
                    response = history_table.scan(**scan_kwargs)
                    
                    for item in response.get('Items', []):
                        unique_repos.add(item['repository_name'])
                    
                    # Check if there's more data to scan
                    if 'LastEvaluatedKey' not in response:
                        break
                        
                    # Set up for next scan page
                    scan_kwargs['ExclusiveStartKey'] = response['LastEvaluatedKey']
                    
                logger.info(f"Dashboard scan: Found {len(unique_repos)} total repositories")
            except Exception as e:
                logger.warning(f"Could not get full repository count: {e}")
        
        dashboard_data = {
            'total_repositories': len(unique_repos),
            'recent_backups': {
                'total': len(total_backup_events),
                'successful': len(successful_backups),
                'failed': len(failed_backups),
                'started': len(started_backups),
                'in_progress': len(in_progress_backups),
                'success_rate': round((len(successful_backups) / len(final_backup_events) * 100) if final_backup_events else 0, 1)
            },
            'recent_events': recent_events[:10],  # Last 10 events
            'last_updated': datetime.now(timezone.utc).isoformat()
        }
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
                'Cache-Control': 'max-age=120'  # Cache for 2 minutes
            },
            'body': json_dumps(dashboard_data)
        }
        
    except Exception as e:
        logger.error(f"Error getting dashboard data: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json_dumps({'error': str(e)})
        }
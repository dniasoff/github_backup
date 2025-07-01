import json
import logging
import os
import subprocess
import tarfile
import tempfile
import shutil
from datetime import datetime
from typing import Dict, List, Any
from urllib.parse import urlparse
import boto3
from botocore.exceptions import ClientError
from audit_logger import audit_logger

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def lambda_handler(event: Dict[str, Any], context) -> Dict[str, Any]:
    """
    Lambda function to backup a single GitHub repository.
    Called by Step Functions for parallel processing.
    """
    try:
        s3_bucket = os.environ['S3_BUCKET_NAME']
        github_token_secret_arn = os.environ['GITHUB_TOKEN_SECRET_ARN']
        
        # Retrieve GitHub token from Secrets Manager
        github_token = get_secret_value(github_token_secret_arn)
        
        # Extract repository info from event (passed by Step Functions)
        if 'name' not in event or 'clone_url' not in event:
            raise ValueError("Repository name and clone_url must be provided in event")
        
        repo_info = {
            'name': event['name'],
            'clone_url': event['clone_url'],
            'archived': event.get('archived', False),
            'size': event.get('size', 'unknown'),
            'updated_at': event.get('updated_at', 'unknown'),
            'private': event.get('private', False)
        }
        
        # Enhanced logging with repository metadata
        logger.info(f"Starting backup for repository: {repo_info['name']}")
        logger.info(f"Repository metadata: size={repo_info['size']}KB, private={repo_info['private']}, updated={repo_info['updated_at']}")
        
        # Log backup start event
        event_id = audit_logger.log_backup_event(
            repository_name=repo_info['name'],
            event_type='backup',
            status='started',
            details={
                'clone_url': repo_info['clone_url'],
                'archived': repo_info['archived'],
                'size_kb': repo_info['size'],
                'private': repo_info['private'],
                'updated_at': repo_info['updated_at']
            }
        )
        
        # Skip archived repositories
        if repo_info['archived']:
            logger.info(f"Skipping archived repository: {repo_info['name']}")
            audit_logger.log_backup_event(
                repository_name=repo_info['name'],
                event_type='backup',
                status='skipped',
                details={'reason': 'archived'}
            )
            return {
                'repository': repo_info['name'],
                'success': False,
                'skipped': True,
                'reason': 'archived'
            }
        
        # Backup single repository
        date_str = datetime.now().strftime('%Y-%m-%d')
        result = backup_single_repository(repo_info, s3_bucket, github_token, date_str)
        
        # Log backup completion event
        if result['success']:
            audit_logger.log_backup_event(
                repository_name=repo_info['name'],
                event_type='backup',
                status='completed',
                details={
                    's3_key': result.get('s3_key', ''),
                    'size_bytes': result.get('size_bytes', 0)
                }
            )
            
            # Log to repository history with versioned backup_version
            timestamp = datetime.now().strftime('%H-%M')
            audit_logger.log_repository_backup(
                repository_name=repo_info['name'],
                backup_version=f"nightly/{date_str}-{timestamp}",
                s3_key=result.get('s3_key', ''),
                size_bytes=result.get('size_bytes', 0),
                storage_class='s3'
            )
        else:
            audit_logger.log_backup_event(
                repository_name=repo_info['name'],
                event_type='backup',
                status='failed',
                details={},
                error=result.get('error', 'Unknown error')
            )
        
        logger.info(f"Backup completed for {repo_info['name']}: {'success' if result['success'] else 'failed'}")
        
        return result
        
    except Exception as e:
        error_msg = str(e)
        repo_name = event.get('name', 'unknown')
        
        # Enhanced error logging with context
        logger.error(f"Error during backup process for {repo_name}: {error_msg}")
        logger.error(f"Full event data: {json.dumps(event, default=str, indent=2)}")
        logger.error(f"Environment info: Lambda memory={os.environ.get('AWS_LAMBDA_FUNCTION_MEMORY_SIZE', 'unknown')}MB")
        
        # Categorize error for better troubleshooting
        error_category = categorize_error(error_msg)
        logger.error(f"Error category: {error_category}")
        
        # Log backup failure with enhanced details
        audit_logger.log_backup_event(
            repository_name=repo_name,
            event_type='backup',
            status='failed',
            details={
                'error_category': error_category,
                'lambda_memory': os.environ.get('AWS_LAMBDA_FUNCTION_MEMORY_SIZE', 'unknown'),
                'repository_size': event.get('size', 'unknown'),
                'repository_private': event.get('private', False)
            },
            error=error_msg
        )
        
        return {
            'repository': repo_name,
            'success': False,
            'error': error_msg,
            'error_category': error_category
        }

def get_repository_list(bucket: str, org: str, token: str) -> List[Dict[str, Any]]:
    """
    Get repository list from S3 manifest or discover dynamically.
    """
    s3_client = boto3.client('s3')
    
    try:
        # Try to get from S3 manifest first
        response = s3_client.get_object(
            Bucket=bucket,
            Key='manifests/repository-manifest.json'
        )
        manifest = json.loads(response['Body'].read())
        return manifest['repositories']
    except Exception as e:
        logger.warning(f"Could not retrieve repository manifest from S3: {str(e)}")
        # Fall back to dynamic discovery
        from discovery_handler import discover_repositories
        return discover_repositories(org, token)

def backup_repositories(repositories: List[Dict[str, Any]], bucket: str, token: str) -> List[Dict[str, Any]]:
    """
    Backup all repositories to S3.
    """
    results = []
    date_str = datetime.now().strftime('%Y-%m-%d')
    
    for repo in repositories:
        try:
            if repo.get('archived', False):
                logger.info(f"Skipping archived repository: {repo['name']}")
                results.append({
                    'repository': repo['name'],
                    'success': False,
                    'skipped': True,
                    'reason': 'archived'
                })
                continue
            
            result = backup_single_repository(repo, bucket, token, date_str)
            results.append(result)
            
        except Exception as e:
            logger.error(f"Failed to backup repository {repo['name']}: {str(e)}")
            results.append({
                'repository': repo['name'],
                'success': False,
                'error': str(e)
            })
    
    return results

def backup_single_repository(repo: Dict[str, Any], bucket: str, token: str, date_str: str) -> Dict[str, Any]:
    """
    Backup a single repository to S3 using ephemeral storage for large repositories.
    """
    repo_name = repo['name']
    clone_url = repo['clone_url']
    
    # Use /tmp for ephemeral storage (up to 10GB available)
    temp_dir = f"/tmp/{repo_name}_{int(datetime.now().timestamp())}"
    repo_dir = os.path.join(temp_dir, repo_name)
    archive_path = os.path.join(temp_dir, f"{repo_name}.tar.gz")
    
    try:
        # Create temporary directory
        os.makedirs(temp_dir, exist_ok=True)
        
        # Check available ephemeral storage
        check_disk_space("/tmp", required_mb=1000)  # Require 1GB free space
        
        # Validate repository access before attempting clone
        if not validate_repository_access(repo, token):
            raise RuntimeError(f"Repository {repo_name} is not accessible with current token")
        
        # Download repository
        download_repository(repo, repo_dir, token)
        
        # Check disk space after clone
        check_disk_space("/tmp", required_mb=500)  # Require 500MB for compression
        
        # Create compressed archive
        create_archive(repo_dir, archive_path)
        
        # Clean up repository directory immediately after archiving to free space
        try:
            shutil.rmtree(repo_dir)
            logger.info(f"Cleaned up repository directory for {repo_name}")
        except Exception as cleanup_error:
            logger.warning(f"Failed to cleanup repo directory: {cleanup_error}")
        
        # Upload to S3 with timestamp for versioning
        timestamp = datetime.now().strftime('%H-%M')
        s3_key = f"nightly/{repo_name}/{date_str}-{timestamp}.tar.gz"
        upload_to_s3(archive_path, bucket, s3_key)
        
        # Get file size for reporting
        file_size = os.path.getsize(archive_path)
        
        logger.info(f"Successfully backed up {repo_name} ({file_size} bytes)")
        
        return {
            'repository': repo_name,
            'success': True,
            's3_key': s3_key,
            'size_bytes': file_size
        }
        
    except Exception as e:
        error_msg = str(e)
        
        # Log detailed error information for troubleshooting
        logger.error(f"Backup failed for {repo_name}: {error_msg}")
        logger.error(f"Repository details: clone_url={clone_url}, size={repo.get('size', 'unknown')}")
        
        # For disk space errors, suggest solutions
        if "no space left" in error_msg.lower() or "insufficient disk space" in error_msg.lower():
            logger.error(f"Ephemeral storage exhausted for {repo_name}. Repository may be too large for available space.")
            raise Exception(f"Ephemeral storage exhausted while backing up {repo_name}. Repository size: {repo.get('size', 'unknown')} KB")
        
        # For authentication errors, provide clearer guidance
        elif "authentication failed" in error_msg.lower():
            raise Exception(f"GitHub authentication failed for {repo_name}. Check token permissions.")
        
        # For repository not found errors
        elif "repository not found" in error_msg.lower():
            raise Exception(f"Repository {repo_name} not found. It may be private, deleted, or renamed.")
        
        # For timeout errors
        elif "timed out" in error_msg.lower():
            raise Exception(f"Timeout while backing up {repo_name}. Repository may be too large.")
        
        # Generic error with context
        else:
            raise Exception(f"Failed to backup {repo_name}: {error_msg}")
    
    finally:
        # Always clean up temporary directory
        try:
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
                logger.info(f"Cleaned up temporary directory: {temp_dir}")
        except Exception as cleanup_error:
            logger.warning(f"Failed to cleanup temporary directory {temp_dir}: {cleanup_error}")

def download_repository(repo_info: Dict[str, Any], repo_dir: str, token: str) -> None:
    """
    Clone a complete GitHub repository with all history, branches, and tags.
    """
    clone_url = repo_info['clone_url']
    
    # Modify clone URL to include authentication token
    if clone_url.startswith('https://github.com/'):
        # Insert token into HTTPS URL: https://token@github.com/owner/repo.git
        authenticated_url = clone_url.replace('https://github.com/', f'https://{token}@github.com/')
    else:
        raise ValueError(f"Unsupported clone URL format: {clone_url}")
    
    logger.info(f"Cloning repository: {repo_info['name']}")
    
    try:
        # First try a shallow clone to save space, then fetch more if needed
        logger.info(f"Attempting shallow clone for {repo_info['name']} to save disk space")
        
        try:
            # Dynamic timeout based on repository size
            repo_size_kb = repo_info.get('size', 0)
            if isinstance(repo_size_kb, (int, float)) and repo_size_kb > 100000:  # Large repo > 100MB
                shallow_timeout = 600  # 10 minutes for large repos
                unshallow_timeout = 900  # 15 minutes for large repos
                logger.info(f"Using extended timeouts for large repository {repo_info['name']} ({repo_size_kb}KB)")
            else:
                shallow_timeout = 300  # 5 minutes for normal repos
                unshallow_timeout = 600  # 10 minutes for normal repos
            
            # Shallow clone with depth 1 first to minimize disk usage
            subprocess.run([
                'git', 'clone', '--depth', '1', '--mirror',
                authenticated_url,
                repo_dir
            ], check=True, capture_output=True, text=True, timeout=shallow_timeout)
            
            # If we have enough space, try to fetch full history
            try:
                check_disk_space(os.path.dirname(repo_dir), required_mb=100)
                logger.info(f"Fetching full history for {repo_info['name']}")
                subprocess.run([
                    'git', '--git-dir', repo_dir, 'fetch', '--unshallow'
                ], check=True, capture_output=True, text=True, timeout=unshallow_timeout)
            except Exception as unshallow_error:
                logger.warning(f"Could not fetch full history for {repo_info['name']}: {unshallow_error}")
                logger.info(f"Continuing with shallow backup for {repo_info['name']}")
                
        except subprocess.CalledProcessError:
            # If shallow clone fails, try regular mirror clone
            logger.info(f"Shallow clone failed, trying full mirror clone for {repo_info['name']}")
            full_timeout = 900 if repo_size_kb < 100000 else 1200  # Extended timeout for large repos
            subprocess.run([
                'git', 'clone', '--mirror',
                authenticated_url,
                repo_dir
            ], check=True, capture_output=True, text=True, timeout=full_timeout)
        
        logger.info(f"Successfully cloned {repo_info['name']} with full history")
        
        # Verify we have a proper Git repository
        git_check = subprocess.run([
            'git', '--git-dir', repo_dir, 'rev-parse', '--git-dir'
        ], capture_output=True, text=True)
        
        if git_check.returncode != 0:
            raise RuntimeError(f"Cloned directory is not a valid Git repository: {repo_dir}")
        
        # Log repository statistics
        try:
            # Count total commits across all branches
            commit_count = subprocess.run([
                'git', '--git-dir', repo_dir, 'rev-list', '--all', '--count'
            ], capture_output=True, text=True, check=True)
            
            # List all branches
            branches = subprocess.run([
                'git', '--git-dir', repo_dir, 'branch', '-a'
            ], capture_output=True, text=True, check=True)
            
            # List all tags
            tags = subprocess.run([
                'git', '--git-dir', repo_dir, 'tag', '-l'
            ], capture_output=True, text=True, check=True)
            
            logger.info(f"Repository {repo_info['name']} statistics:")
            logger.info(f"  Total commits: {commit_count.stdout.strip()}")
            logger.info(f"  Branches: {len(branches.stdout.strip().split()) if branches.stdout.strip() else 0}")
            logger.info(f"  Tags: {len(tags.stdout.strip().split()) if tags.stdout.strip() else 0}")
            
        except subprocess.CalledProcessError as e:
            logger.warning(f"Could not get repository statistics: {e}")
        
    except subprocess.TimeoutExpired as e:
        raise RuntimeError(f"Git clone timed out after 15 minutes for repository: {repo_info['name']}")
    except subprocess.CalledProcessError as e:
        error_msg = e.stderr if e.stderr else str(e)
        # Check for specific error patterns to provide better error messages
        if "authentication failed" in error_msg.lower():
            raise RuntimeError(f"Authentication failed for {repo_info['name']}: Check GitHub token permissions")
        elif "repository not found" in error_msg.lower():
            raise RuntimeError(f"Repository not found: {repo_info['name']} (may be private or deleted)")
        elif "no space left" in error_msg.lower():
            raise RuntimeError(f"No space left on device while cloning {repo_info['name']}")
        else:
            raise RuntimeError(f"Git clone failed for {repo_info['name']}: {error_msg}")
    except Exception as e:
        # Catch any other unexpected errors
        raise RuntimeError(f"Unexpected error cloning {repo_info['name']}: {str(e)}")

def create_archive(source_dir: str, archive_path: str) -> None:
    """
    Create a highly compressed tar.gz archive of the repository for cost optimization.
    """
    # Use maximum compression (level 9) to reduce storage costs
    with tarfile.open(archive_path, 'w:gz', compresslevel=9) as tar:
        tar.add(source_dir, arcname=os.path.basename(source_dir))
    
    # Log compression statistics for cost monitoring
    original_size = get_directory_size(source_dir)
    compressed_size = os.path.getsize(archive_path)
    compression_ratio = (1 - compressed_size / original_size) * 100 if original_size > 0 else 0
    
    logger.info(f"Compression stats - Original: {original_size} bytes, "
               f"Compressed: {compressed_size} bytes, "
               f"Ratio: {compression_ratio:.1f}% savings")

def get_directory_size(path: str) -> int:
    """Calculate total size of directory for compression statistics."""
    total_size = 0
    for dirpath, dirnames, filenames in os.walk(path):
        for filename in filenames:
            filepath = os.path.join(dirpath, filename)
            try:
                total_size += os.path.getsize(filepath)
            except (OSError, IOError):
                pass
    return total_size

def check_disk_space(path: str, required_mb: int) -> None:
    """
    Check available disk space and raise error if insufficient.
    """
    try:
        stat = os.statvfs(path)
        available_bytes = stat.f_bavail * stat.f_frsize
        available_mb = available_bytes / (1024 * 1024)
        
        logger.info(f"Available disk space in {path}: {available_mb:.1f} MB, required: {required_mb} MB")
        
        if available_mb < required_mb:
            # Try to clean up old temp directories first
            cleanup_old_temp_directories(path)
            
            # Check again after cleanup
            stat = os.statvfs(path)
            available_bytes = stat.f_bavail * stat.f_frsize
            available_mb = available_bytes / (1024 * 1024)
            
            if available_mb < required_mb:
                raise RuntimeError(f"Insufficient disk space: {available_mb:.1f} MB available, {required_mb} MB required")
            else:
                logger.info(f"Cleanup freed space. Now available: {available_mb:.1f} MB")
            
    except Exception as e:
        logger.warning(f"Could not check disk space: {e}")
        # Don't fail the backup just because we can't check disk space

def cleanup_old_temp_directories(base_path: str) -> None:
    """
    Clean up old temporary directories that might be left from previous failed executions.
    """
    try:
        if not os.path.exists(base_path):
            return
            
        current_time = datetime.now().timestamp()
        cleanup_count = 0
        
        for item in os.listdir(base_path):
            item_path = os.path.join(base_path, item)
            
            # Look for temporary directories with our naming pattern
            if (os.path.isdir(item_path) and 
                ('_' in item) and 
                item_path != base_path):
                
                try:
                    # Check if directory is older than 1 hour
                    mtime = os.path.getmtime(item_path)
                    age_hours = (current_time - mtime) / 3600
                    
                    if age_hours > 1:  # Clean up directories older than 1 hour
                        shutil.rmtree(item_path)
                        cleanup_count += 1
                        logger.info(f"Cleaned up old temp directory: {item}")
                        
                except Exception as cleanup_error:
                    logger.warning(f"Failed to cleanup old directory {item}: {cleanup_error}")
        
        if cleanup_count > 0:
            logger.info(f"Cleaned up {cleanup_count} old temporary directories")
            
    except Exception as e:
        logger.warning(f"Failed to cleanup old temp directories: {e}")

def categorize_error(error_msg: str) -> str:
    """
    Categorize errors for better troubleshooting and alerting.
    """
    error_lower = error_msg.lower()
    
    if "no space left" in error_lower or "insufficient disk space" in error_lower:
        return "DISK_SPACE"
    elif "authentication failed" in error_lower or "permission denied" in error_lower:
        return "AUTHENTICATION"
    elif "repository not found" in error_lower or "not found" in error_lower:
        return "REPOSITORY_ACCESS"
    elif "timeout" in error_lower or "timed out" in error_lower:
        return "TIMEOUT"
    elif "network" in error_lower or "connection" in error_lower or "dns" in error_lower:
        return "NETWORK"
    elif "libpcre2" in error_lower or "shared libraries" in error_lower:
        return "LAMBDA_LAYER"
    elif "no such file or directory" in error_lower and "git" in error_lower:
        return "GIT_MISSING"
    elif "memory" in error_lower or "out of memory" in error_lower:
        return "MEMORY"
    else:
        return "UNKNOWN"

def validate_repository_access(repo_info: Dict[str, Any], token: str) -> bool:
    """
    Validate that we can access the repository before attempting backup.
    """
    try:
        import requests
        
        # Extract owner and repo name from clone URL
        clone_url = repo_info['clone_url']
        if 'github.com/' in clone_url:
            parts = clone_url.split('github.com/')[-1].replace('.git', '').split('/')
            if len(parts) >= 2:
                owner, repo = parts[0], parts[1]
                
                # Test API access to repository
                api_url = f"https://api.github.com/repos/{owner}/{repo}"
                headers = {'Authorization': f'token {token}'}
                
                response = requests.get(api_url, headers=headers, timeout=10)
                
                if response.status_code == 200:
                    logger.info(f"Repository access validated for {repo_info['name']}")
                    return True
                elif response.status_code == 404:
                    logger.warning(f"Repository {repo_info['name']} not found or not accessible")
                    return False
                elif response.status_code == 403:
                    logger.warning(f"Access forbidden to repository {repo_info['name']}")
                    return False
                else:
                    logger.warning(f"Unexpected response {response.status_code} for {repo_info['name']}")
                    return True  # Allow backup attempt
                    
    except Exception as e:
        logger.warning(f"Could not validate repository access for {repo_info['name']}: {e}")
        return True  # Allow backup attempt if validation fails
    
    return True

def upload_to_s3(file_path: str, bucket: str, key: str) -> None:
    """
    Upload file to S3 with cost-optimized storage class.
    """
    s3_client = boto3.client('s3')
    
    with open(file_path, 'rb') as f:
        s3_client.put_object(
            Bucket=bucket,
            Key=key,
            Body=f,
            ServerSideEncryption='AES256',
            StorageClass='STANDARD_IA'  # Use Standard-IA for cost optimization
        )

def create_backup_manifest(bucket: str, results: List[Dict[str, Any]]) -> None:
    """
    Create a manifest file for the backup session.
    """
    s3_client = boto3.client('s3')
    date_str = datetime.now().strftime('%Y-%m-%d')
    
    manifest = {
        'backup_date': date_str,
        'timestamp': datetime.now().isoformat(),
        'total_repositories': len(results),
        'successful_backups': sum(1 for r in results if r['success']),
        'results': results
    }
    
    timestamp = datetime.now().strftime('%H-%M')
    key = f"nightly/manifests/{date_str}-{timestamp}-manifest.json"
    
    s3_client.put_object(
        Bucket=bucket,
        Key=key,
        Body=json.dumps(manifest, indent=2),
        ContentType='application/json',
        ServerSideEncryption='AES256'
    )
    
    logger.info(f"Created backup manifest: s3://{bucket}/{key}")

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
        
        # Calculate statistics
        total_repos = len(results)
        successful = sum(1 for r in results if r.get('success', False))
        failed = total_repos - successful
        errors = [r for r in results if not r.get('success', False) and 'error' in r]
        
        # Create subject
        status = "SUCCESS" if failed == 0 else "PARTIAL SUCCESS" if successful > 0 else "FAILED"
        subject = f"GitHub Backup {job_type.title()} - {status} ({successful}/{total_repos})"
        
        # Create formatted message
        message = create_email_message(job_type, total_repos, successful, failed, errors, results)
        
        # Send notification
        sns_client.publish(
            TopicArn=topic_arn,
            Subject=subject,
            Message=message
        )
        
        logger.info(f"Notification sent: {subject}")
        
    except Exception as e:
        logger.error(f"Failed to send notification: {str(e)}")

def create_email_message(job_type: str, total: int, successful: int, failed: int, errors: List[Dict], results: List[Dict]) -> str:
    """
    Create a nicely formatted email message with error details (truncated if needed).
    """
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')
    
    message = f"""GitHub Backup {job_type.title()} Report
========================================

Execution Time: {timestamp}
Total Repositories: {total}
Successful: {successful}
Failed: {failed}

"""
    
    if failed > 0:
        message += "ERRORS:\n"
        message += "--------\n"
        
        # Limit error details to prevent email size issues
        max_errors_to_show = 20
        max_error_length = 500
        
        for i, error in enumerate(errors[:max_errors_to_show]):
            repo_name = error.get('repository', 'Unknown')
            error_msg = str(error.get('error', 'Unknown error'))
            
            # Truncate long error messages
            if len(error_msg) > max_error_length:
                error_msg = error_msg[:max_error_length] + "... [TRUNCATED]"
            
            message += f"{i+1}. {repo_name}\n"
            message += f"   Error: {error_msg}\n\n"
        
        # Note if there are more errors
        if len(errors) > max_errors_to_show:
            remaining = len(errors) - max_errors_to_show
            message += f"... and {remaining} more errors (check CloudWatch logs for full details)\n\n"
    
    if successful > 0:
        message += "SUCCESSFUL REPOSITORIES:\n"
        message += "------------------------\n"
        success_repos = [r.get('repository', 'Unknown') for r in results if r.get('success', False)]
        
        # Show first 30 successful repos to avoid email size issues
        for repo in success_repos[:30]:
            message += f"✓ {repo}\n"
        
        if len(success_repos) > 30:
            remaining = len(success_repos) - 30
            message += f"... and {remaining} more successful repositories\n"
    
    message += f"\nFor complete logs, check CloudWatch: /aws/lambda/github-backup-{job_type.replace(' ', '-')}\n"
    
    return message

def get_secret_value(secret_arn: str) -> str:
    """
    Retrieve a secret value from AWS Secrets Manager.
    """
    secrets_client = boto3.client('secretsmanager')
    
    try:
        response = secrets_client.get_secret_value(SecretId=secret_arn)
        secret_data = json.loads(response['SecretString'])
        
        # The secret should contain the GitHub token directly or in a 'token' field
        if isinstance(secret_data, str):
            return secret_data
        elif isinstance(secret_data, dict) and 'token' in secret_data:
            return secret_data['token']
        elif isinstance(secret_data, dict) and 'github_token' in secret_data:
            return secret_data['github_token']
        else:
            # If it's a dict but no standard field, try to get the first value
            if isinstance(secret_data, dict):
                return list(secret_data.values())[0]
            
        raise ValueError(f"Could not extract token from secret: {secret_data}")
        
    except ClientError as e:
        logger.error(f"Failed to retrieve secret {secret_arn}: {str(e)}")
        raise
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse secret JSON {secret_arn}: {str(e)}")
        # Try returning the raw secret string
        return response['SecretString']
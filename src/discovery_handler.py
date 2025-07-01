import json
import logging
import os
from datetime import datetime
from typing import Dict, List, Any
import boto3
import requests
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def lambda_handler(event: Dict[str, Any], context) -> Dict[str, Any]:
    """
    Lambda function to discover all repositories in a GitHub organization.
    Retrieves GitHub token from AWS Secrets Manager and lists all repositories.
    """
    try:
        github_org = os.environ['GITHUB_ORG']
        s3_bucket = os.environ['S3_BUCKET_NAME']
        github_token_secret_arn = os.environ['GITHUB_TOKEN_SECRET_ARN']
        
        # Retrieve GitHub token from Secrets Manager
        github_token = get_secret_value(github_token_secret_arn)
        
        # Discover repositories
        repositories = discover_repositories(github_org, github_token)
        
        # Store repository list in S3 for other Lambda functions
        store_repository_manifest(s3_bucket, repositories)
        
        logger.info(f"Discovered {len(repositories)} repositories in organization {github_org}")
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': f'Successfully discovered {len(repositories)} repositories',
                'repositories': repositories
            })
        }
        
    except Exception as e:
        logger.error(f"Error discovering repositories: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': f'Failed to discover repositories: {str(e)}'
            })
        }

def discover_repositories(org: str, token: str) -> List[Dict[str, Any]]:
    """
    Discover all repositories in a GitHub organization using the GitHub API.
    """
    headers = {
        'Authorization': f'token {token}',
        'Accept': 'application/vnd.github.v3+json'
    }
    
    repositories = []
    page = 1
    per_page = 100
    
    while True:
        url = f'https://api.github.com/orgs/{org}/repos'
        params = {
            'page': page,
            'per_page': per_page,
            'type': 'all',
            'sort': 'updated'
        }
        
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        
        repos = response.json()
        if not repos:
            break
            
        for repo in repos:
            repositories.append({
                'name': repo['name'],
                'full_name': repo['full_name'],
                'clone_url': repo['clone_url'],
                'ssh_url': repo['ssh_url'],
                'default_branch': repo['default_branch'],
                'updated_at': repo['updated_at'],
                'size': repo['size'],
                'archived': repo['archived'],
                'private': repo['private']
            })
        
        page += 1
    
    return repositories

def store_repository_manifest(bucket: str, repositories: List[Dict[str, Any]]) -> None:
    """
    Store the repository manifest in S3 for other Lambda functions to use.
    """
    s3_client = boto3.client('s3')
    
    manifest = {
        'timestamp': datetime.now().isoformat(),
        'total_repositories': len(repositories),
        'repositories': repositories
    }
    
    key = 'manifests/repository-manifest.json'
    
    s3_client.put_object(
        Bucket=bucket,
        Key=key,
        Body=json.dumps(manifest, indent=2),
        ContentType='application/json'
    )
    
    logger.info(f"Stored repository manifest in s3://{bucket}/{key}")

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
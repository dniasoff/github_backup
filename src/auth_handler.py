import json
import logging
import os
import jwt
import hashlib
import hmac
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional
import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def lambda_handler(event: Dict[str, Any], context) -> Dict[str, Any]:
    """
    Lambda function to handle authentication for the GitHub backup UI.
    Supports login and token validation.
    """
    try:
        # Parse API Gateway event
        http_method = event.get('httpMethod', '')
        resource_path = event.get('resource', '')
        body = event.get('body', '')
        headers = event.get('headers', {})
        
        logger.info(f"Auth request: {http_method} {resource_path}")
        
        # Route to appropriate handler
        if resource_path == '/auth/login' and http_method == 'POST':
            return handle_login(json.loads(body) if body else {})
        
        elif resource_path == '/auth/validate' and http_method == 'POST':
            return handle_token_validation(headers)
        
        elif resource_path == '/auth/logout' and http_method == 'POST':
            return handle_logout()
        
        else:
            return {
                'statusCode': 404,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({'error': 'Auth endpoint not found'})
            }
            
    except Exception as e:
        logger.error(f"Auth error: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({'error': f'Authentication error: {str(e)}'})
        }

def handle_login(request_body: Dict[str, Any]) -> Dict[str, Any]:
    """Handle user login and JWT token generation."""
    try:
        username = request_body.get('username', '').strip()
        password = request_body.get('password', '').strip()
        
        if not username or not password:
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({'error': 'Username and password are required'})
            }
        
        # Get stored credentials from AWS Secrets Manager
        secrets_client = boto3.client('secretsmanager')
        
        try:
            auth_secret = secrets_client.get_secret_value(
                SecretId=os.environ['AUTH_SECRET_ARN']
            )
            auth_data = json.loads(auth_secret['SecretString'])
            stored_username = auth_data['username']
            stored_password = auth_data['password']
        except ClientError as e:
            logger.error(f"Failed to retrieve auth credentials: {str(e)}")
            return {
                'statusCode': 500,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({'error': 'Authentication service unavailable'})
            }
        
        # Verify credentials using constant-time comparison
        username_match = hmac.compare_digest(username, stored_username)
        password_match = hmac.compare_digest(password, stored_password)
        
        if not (username_match and password_match):
            return {
                'statusCode': 401,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({'error': 'Invalid username or password'})
            }
        
        # Get JWT signing secret
        try:
            jwt_secret_response = secrets_client.get_secret_value(
                SecretId=os.environ['JWT_SECRET_ARN']
            )
            jwt_data = json.loads(jwt_secret_response['SecretString'])
            jwt_secret = jwt_data['jwt_secret']
        except ClientError as e:
            logger.error(f"Failed to retrieve JWT secret: {str(e)}")
            return {
                'statusCode': 500,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({'error': 'Token generation failed'})
            }
        
        # Generate JWT token
        now = datetime.now(timezone.utc)
        expiry = now + timedelta(hours=8)  # 8-hour session
        
        payload = {
            'sub': username,
            'iat': int(now.timestamp()),
            'exp': int(expiry.timestamp()),
            'iss': 'github-backup-ui',
            'aud': 'github-backup-api'
        }
        
        token = jwt.encode(payload, jwt_secret, algorithm='HS256')
        
        logger.info(f"Successful login for user: {username}")
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'success': True,
                'token': token,
                'username': username,
                'expires_at': expiry.isoformat(),
                'expires_in': 8 * 3600  # 8 hours in seconds
            })
        }
        
    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({'error': f'Login failed: {str(e)}'})
        }

def handle_token_validation(headers: Dict[str, str]) -> Dict[str, Any]:
    """Validate JWT token from Authorization header."""
    try:
        auth_header = headers.get('Authorization', headers.get('authorization', ''))
        
        if not auth_header.startswith('Bearer '):
            return {
                'statusCode': 401,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({'error': 'Missing or invalid authorization header'})
            }
        
        token = auth_header[7:]  # Remove 'Bearer ' prefix
        
        # Get JWT signing secret
        secrets_client = boto3.client('secretsmanager')
        
        try:
            jwt_secret_response = secrets_client.get_secret_value(
                SecretId=os.environ['JWT_SECRET_ARN']
            )
            jwt_data = json.loads(jwt_secret_response['SecretString'])
            jwt_secret = jwt_data['jwt_secret']
        except ClientError as e:
            logger.error(f"Failed to retrieve JWT secret: {str(e)}")
            return {
                'statusCode': 500,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({'error': 'Token validation failed'})
            }
        
        # Verify and decode token
        try:
            payload = jwt.decode(
                token, 
                jwt_secret, 
                algorithms=['HS256'],
                audience='github-backup-api',
                issuer='github-backup-ui'
            )
            
            username = payload.get('sub')
            exp = payload.get('exp')
            
            # Check if token is still valid
            if exp and datetime.now(timezone.utc).timestamp() > exp:
                return {
                    'statusCode': 401,
                    'headers': {
                        'Content-Type': 'application/json',
                        'Access-Control-Allow-Origin': '*'
                    },
                    'body': json.dumps({'error': 'Token expired'})
                }
            
            return {
                'statusCode': 200,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({
                    'valid': True,
                    'username': username,
                    'expires_at': datetime.fromtimestamp(exp, timezone.utc).isoformat() if exp else None
                })
            }
            
        except jwt.ExpiredSignatureError:
            return {
                'statusCode': 401,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({'error': 'Token expired'})
            }
        
        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid token: {str(e)}")
            return {
                'statusCode': 401,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({'error': 'Invalid token'})
            }
        
    except Exception as e:
        logger.error(f"Token validation error: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({'error': f'Token validation failed: {str(e)}'})
        }

def handle_logout() -> Dict[str, Any]:
    """Handle user logout (client-side token removal)."""
    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*'
        },
        'body': json.dumps({
            'success': True,
            'message': 'Logged out successfully'
        })
    }

def validate_token_for_api(token: str) -> Optional[Dict[str, Any]]:
    """
    Utility function to validate token for other API endpoints.
    Returns payload if valid, None if invalid.
    """
    try:
        secrets_client = boto3.client('secretsmanager')
        
        jwt_secret_response = secrets_client.get_secret_value(
            SecretId=os.environ['JWT_SECRET_ARN']
        )
        jwt_data = json.loads(jwt_secret_response['SecretString'])
        jwt_secret = jwt_data['jwt_secret']
        
        payload = jwt.decode(
            token, 
            jwt_secret, 
            algorithms=['HS256'],
            audience='github-backup-api',
            issuer='github-backup-ui'
        )
        
        return payload
        
    except Exception as e:
        logger.warning(f"Token validation failed: {str(e)}")
        return None
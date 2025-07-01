import json
import logging
import os
from datetime import datetime
from typing import Dict, List, Any
import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def lambda_handler(event: Dict[str, Any], context) -> Dict[str, Any]:
    """
    Lambda function to format backup results into beautiful HTML emails.
    Triggered by Step Functions to send formatted notifications.
    """
    try:
        # Parse the backup results
        backup_data = event
        
        # Generate beautiful HTML email
        html_content = generate_email_html(backup_data)
        text_content = generate_email_text(backup_data)
        
        # Send formatted email via SNS
        sns_client = boto3.client('sns')
        topic_arn = os.environ['SNS_TOPIC_ARN']
        
        # Create the email message
        subject = generate_email_subject(backup_data)
        
        # Send the formatted email
        response = sns_client.publish(
            TopicArn=topic_arn,
            Subject=subject,
            Message=text_content,
            MessageAttributes={
                'email.content.type': {
                    'DataType': 'String',
                    'StringValue': 'text/html'
                }
            }
        )
        
        logger.info(f"Formatted email sent successfully. MessageId: {response['MessageId']}")
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Formatted email sent successfully',
                'messageId': response['MessageId']
            })
        }
        
    except Exception as e:
        logger.error(f"Error sending formatted email: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': f'Failed to send formatted email: {str(e)}'
            })
        }

def generate_email_subject(data: Dict[str, Any]) -> str:
    """Generate a concise, informative email subject."""
    total = data.get('total_repositories', 0)
    successful = data.get('successful_backups', 0)
    failed = total - successful
    
    if failed == 0:
        return f"✅ GitHub Backup Complete - All {total} repositories backed up successfully"
    elif successful == 0:
        return f"❌ GitHub Backup Failed - {total} repositories failed"
    else:
        return f"⚠️ GitHub Backup Partial - {successful}/{total} successful, {failed} failed"

def generate_email_html(data: Dict[str, Any]) -> str:
    """Generate a beautiful, mobile-friendly HTML email."""
    total = data.get('total_repositories', 0)
    successful = data.get('successful_backups', 0)
    backup_date = data.get('backup_date', '')
    results = data.get('results', [])
    
    # Calculate actual failures (excluding skipped repos)
    actual_failures = [r for r in results if not r.get('success') and not r.get('skipped')]
    failed = len(actual_failures)
    
    # Parse backup date
    try:
        dt = datetime.fromisoformat(backup_date.replace('Z', '+00:00'))
        formatted_date = dt.strftime('%B %d, %Y at %H:%M UTC')
    except:
        formatted_date = backup_date
    
    # Calculate total size
    total_size = sum(result.get('size_bytes', 0) for result in results if result.get('success'))
    size_mb = total_size / (1024 * 1024)
    
    # Determine status and colors
    if failed == 0:
        status_icon = "✅"
        status_text = "COMPLETED SUCCESSFULLY"
        status_color = "#10B981"
        bg_color = "#ECFDF5"
    elif successful == 0:
        status_icon = "❌"
        status_text = "FAILED"
        status_color = "#EF4444"
        bg_color = "#FEF2F2"
    else:
        status_icon = "⚠️"
        status_text = "PARTIALLY COMPLETED"
        status_color = "#F59E0B"
        bg_color = "#FFFBEB"
    
    # Generate failed repositories list (exclude skipped/archived repos)
    failed_repos = []
    successful_repos = []
    skipped_repos = []
    
    for result in results:
        if result.get('success'):
            size_mb_repo = result.get('size_bytes', 0) / (1024 * 1024)
            successful_repos.append({
                'name': result.get('repository', 'Unknown'),
                'size': f"{size_mb_repo:.1f} MB"
            })
        elif result.get('skipped'):
            # Track skipped repos separately (don't count as failures)
            skipped_repos.append({
                'name': result.get('repository', 'Unknown'),
                'reason': result.get('reason', 'Unknown reason')
            })
        else:
            failed_repos.append({
                'name': result.get('repository', 'Unknown'),
                'error': result.get('error', 'Unknown error')
            })
    
    # Sort repos by size (largest first) for successful ones
    successful_repos.sort(key=lambda x: float(x['size'].replace(' MB', '')), reverse=True)
    
    html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>GitHub Backup Report</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            line-height: 1.6;
            color: #1F2937;
            background-color: #F9FAFB;
        }}
        
        .container {{
            max-width: 600px;
            margin: 0 auto;
            background-color: #FFFFFF;
            border-radius: 12px;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
            overflow: hidden;
        }}
        
        .header {{
            background: linear-gradient(135deg, #667EEA 0%, #764BA2 100%);
            color: white;
            padding: 24px;
            text-align: center;
        }}
        
        .header h1 {{
            font-size: 24px;
            font-weight: 700;
            margin-bottom: 8px;
        }}
        
        .header p {{
            font-size: 16px;
            opacity: 0.9;
        }}
        
        .status-banner {{
            background-color: {bg_color};
            border-left: 4px solid {status_color};
            padding: 16px 24px;
            margin: 0;
        }}
        
        .status-content {{
            display: flex;
            align-items: center;
            gap: 12px;
        }}
        
        .status-icon {{
            font-size: 24px;
        }}
        
        .status-text {{
            font-size: 18px;
            font-weight: 600;
            color: {status_color};
        }}
        
        .summary {{
            padding: 24px;
            background-color: #F8FAFC;
            border-bottom: 1px solid #E5E7EB;
        }}
        
        .summary-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
            gap: 16px;
            margin-top: 16px;
        }}
        
        .summary-card {{
            background: white;
            padding: 16px;
            border-radius: 8px;
            text-align: center;
            border: 1px solid #E5E7EB;
        }}
        
        .summary-number {{
            font-size: 24px;
            font-weight: 700;
            color: #1F2937;
        }}
        
        .summary-label {{
            font-size: 12px;
            color: #6B7280;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-top: 4px;
        }}
        
        .content {{
            padding: 24px;
        }}
        
        .section {{
            margin-bottom: 24px;
        }}
        
        .section h3 {{
            font-size: 18px;
            font-weight: 600;
            color: #1F2937;
            margin-bottom: 12px;
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        
        .repo-list {{
            background-color: #F8FAFC;
            border-radius: 8px;
            overflow: hidden;
        }}
        
        .repo-item {{
            padding: 12px 16px;
            border-bottom: 1px solid #E5E7EB;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        
        .repo-item:last-child {{
            border-bottom: none;
        }}
        
        .repo-name {{
            font-weight: 500;
            color: #1F2937;
        }}
        
        .repo-size {{
            font-size: 14px;
            color: #6B7280;
        }}
        
        .error-item {{
            background-color: #FEF2F2;
            border-left: 3px solid #EF4444;
        }}
        
        .error-text {{
            font-size: 12px;
            color: #7F1D1D;
            margin-top: 4px;
        }}
        
        .footer {{
            background-color: #1F2937;
            color: #9CA3AF;
            padding: 16px 24px;
            text-align: center;
            font-size: 14px;
        }}
        
        .footer a {{
            color: #60A5FA;
            text-decoration: none;
        }}
        
        @media (max-width: 480px) {{
            .container {{
                margin: 0;
                border-radius: 0;
            }}
            
            .summary-grid {{
                grid-template-columns: repeat(2, 1fr);
            }}
            
            .header h1 {{
                font-size: 20px;
            }}
            
            .repo-item {{
                flex-direction: column;
                align-items: flex-start;
                gap: 4px;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🔒 GitHub Backup Report</h1>
            <p>{formatted_date}</p>
        </div>
        
        <div class="status-banner">
            <div class="status-content">
                <span class="status-icon">{status_icon}</span>
                <span class="status-text">{status_text}</span>
            </div>
        </div>
        
        <div class="summary">
            <h2 style="font-size: 20px; color: #1F2937; margin-bottom: 8px;">Backup Summary</h2>
            <div class="summary-grid">
                <div class="summary-card">
                    <div class="summary-number">{total}</div>
                    <div class="summary-label">Total Repositories</div>
                </div>
                <div class="summary-card">
                    <div class="summary-number" style="color: #10B981;">{successful}</div>
                    <div class="summary-label">Successful</div>
                </div>
                <div class="summary-card">
                    <div class="summary-number" style="color: #EF4444;">{failed}</div>
                    <div class="summary-label">Failed</div>
                </div>
                <div class="summary-card">
                    <div class="summary-number">{size_mb:.1f}</div>
                    <div class="summary-label">Total Size (MB)</div>
                </div>
            </div>
        </div>
        
        <div class="content">
    """
    
    # Add successful repositories section if there are any
    if successful_repos:
        html += f"""
            <div class="section">
                <h3>✅ Successfully Backed Up ({len(successful_repos)})</h3>
                <div class="repo-list">
        """
        
        # Show top 10 successful repos
        for repo in successful_repos[:10]:
            html += f"""
                    <div class="repo-item">
                        <span class="repo-name">{repo['name']}</span>
                        <span class="repo-size">{repo['size']}</span>
                    </div>
            """
        
        if len(successful_repos) > 10:
            remaining = len(successful_repos) - 10
            html += f"""
                    <div class="repo-item" style="background-color: #F3F4F6; font-style: italic;">
                        <span class="repo-name">... and {remaining} more repositories</span>
                        <span class="repo-size">✅</span>
                    </div>
            """
        
        html += """
                </div>
            </div>
        """
    
    # Add failed repositories section if there are any
    if failed_repos:
        html += f"""
            <div class="section">
                <h3>❌ Failed Backups ({len(failed_repos)})</h3>
                <div class="repo-list">
        """
        
        for repo in failed_repos:
            error_short = repo['error'][:100] + "..." if len(repo['error']) > 100 else repo['error']
            html += f"""
                    <div class="repo-item error-item">
                        <div>
                            <div class="repo-name">{repo['name']}</div>
                            <div class="error-text">{error_short}</div>
                        </div>
                    </div>
            """
        
        html += """
                </div>
            </div>
        """
    
    # Add skipped repositories section if there are any
    if skipped_repos:
        html += f"""
            <div class="section">
                <h3>⏭️ Skipped Repositories ({len(skipped_repos)})</h3>
                <div class="repo-list">
        """
        
        for repo in skipped_repos:
            html += f"""
                    <div class="repo-item">
                        <div>
                            <div class="repo-name">{repo['name']}</div>
                            <div class="repo-size">Reason: {repo['reason']}</div>
                        </div>
                    </div>
            """
        
        html += """
                </div>
            </div>
        """
    
    html += """
        </div>
        
        <div class="footer">
            <p>GitHub Backup System • Powered by AWS Lambda & Step Functions</p>
            <p style="margin-top: 4px;">
                <a href="https://github.com/your-org/github-backup">View on GitHub</a> • 
                <a href="https://console.aws.amazon.com/s3/">View S3 Backups</a>
            </p>
        </div>
    </div>
</body>
</html>
    """
    
    return html

def generate_email_text(data: Dict[str, Any]) -> str:
    """Generate a plain text version of the email for fallback."""
    total = data.get('total_repositories', 0)
    successful = data.get('successful_backups', 0)
    failed = total - successful
    backup_date = data.get('backup_date', '')
    
    # Parse backup date
    try:
        dt = datetime.fromisoformat(backup_date.replace('Z', '+00:00'))
        formatted_date = dt.strftime('%B %d, %Y at %H:%M UTC')
    except:
        formatted_date = backup_date
    
    # Calculate total size
    results = data.get('results', [])
    total_size = sum(result.get('size_bytes', 0) for result in results if result.get('success'))
    size_mb = total_size / (1024 * 1024)
    
    text = f"""
GitHub Backup Report - {formatted_date}

SUMMARY:
• Total Repositories: {total}
• Successful Backups: {successful}
• Failed Backups: {failed}
• Total Size: {size_mb:.1f} MB

STATUS: {"✅ COMPLETED SUCCESSFULLY" if failed == 0 else "❌ FAILED" if successful == 0 else "⚠️ PARTIALLY COMPLETED"}
"""
    
    if failed > 0:
        text += f"\nFAILED REPOSITORIES ({failed}):\n"
        for result in results:
            if not result.get('success') and not result.get('skipped'):
                text += f"• {result.get('repository', 'Unknown')}: {result.get('error', 'Unknown error')}\n"
    
    # Show skipped repositories separately
    skipped_count = len([r for r in results if r.get('skipped')])
    if skipped_count > 0:
        text += f"\nSKIPPED REPOSITORIES ({skipped_count}):\n"
        for result in results:
            if result.get('skipped'):
                text += f"• {result.get('repository', 'Unknown')}: {result.get('reason', 'Unknown reason')}\n"
    
    text += "\n---\nGitHub Backup System • Powered by AWS"
    
    return text
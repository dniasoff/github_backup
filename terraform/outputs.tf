# Terraform Outputs for GitHub Backup System

# =============================================================================
# WEB INTERFACE & API
# =============================================================================

output "web_interface_url" {
  description = "Primary URL for accessing the web interface"
  value       = "https://${var.custom_domain}"
}

output "web_interface_www_url" {
  description = "WWW URL for accessing the web interface"
  value       = "https://www.${var.custom_domain}"
}

output "cloudfront_url" {
  description = "CloudFront distribution URL"
  value       = "https://${aws_cloudfront_distribution.web_distribution.domain_name}"
}

output "cloudfront_distribution_id" {
  description = "CloudFront Distribution ID"
  value       = aws_cloudfront_distribution.web_distribution.id
}

output "api_gateway_url" {
  description = "URL of the API Gateway"
  value       = "https://${aws_api_gateway_rest_api.backup_api.id}.execute-api.${data.aws_region.current.id}.amazonaws.com/${aws_api_gateway_stage.backup_api_stage.stage_name}"
}

output "api_gateway_id" {
  description = "API Gateway ID"
  value       = aws_api_gateway_rest_api.backup_api.id
}

# =============================================================================
# STORAGE & ARCHIVAL
# =============================================================================

output "s3_bucket_name" {
  description = "Name of the S3 bucket for backups"
  value       = aws_s3_bucket.backup_bucket.bucket
}

output "s3_bucket_arn" {
  description = "ARN of the S3 bucket for backups"
  value       = aws_s3_bucket.backup_bucket.arn
}

output "web_bucket_name" {
  description = "Name of the S3 bucket hosting the web interface"
  value       = aws_s3_bucket.web_hosting.bucket
}

output "glacier_vault_name" {
  description = "Name of the Glacier vault for archives"
  value       = aws_glacier_vault.backup_vault.name
}

output "glacier_vault_arn" {
  description = "ARN of the Glacier vault for archives"
  value       = aws_glacier_vault.backup_vault.arn
}

# =============================================================================
# SSL & DNS
# =============================================================================

output "certificate_arn" {
  description = "ARN of the SSL certificate"
  value       = aws_acm_certificate.web_cert.arn
}

output "dns_zone_id" {
  description = "Route53 hosted zone ID"
  value       = data.aws_route53_zone.main.zone_id
}

output "dns_zone_name" {
  description = "Route53 hosted zone name"
  value       = data.aws_route53_zone.main.name
}

# =============================================================================
# AUTHENTICATION & SECURITY
# =============================================================================

output "backup_ui_username" {
  description = "Username for GitHub backup UI"
  value       = "admin"
}

output "backup_auth_secret_arn" {
  description = "ARN of the AWS Secrets Manager secret containing auth credentials"
  value       = aws_secretsmanager_secret.backup_auth.arn
  sensitive   = true
}

output "jwt_secret_arn" {
  description = "ARN of the JWT signing secret"
  value       = aws_secretsmanager_secret.jwt_secret.arn
  sensitive   = true
}

# =============================================================================
# LAMBDA FUNCTIONS
# =============================================================================

output "discovery_lambda_function_name" {
  description = "Name of the discovery Lambda function"
  value       = aws_lambda_function.discovery_handler.function_name
}

output "backup_lambda_function_name" {
  description = "Name of the backup Lambda function"
  value       = aws_lambda_function.backup_handler.function_name
}

output "archival_lambda_function_name" {
  description = "Name of the archival Lambda function"
  value       = aws_lambda_function.archival_handler.function_name
}

output "lambda_functions" {
  description = "ARNs of all Lambda functions"
  value = {
    discovery         = aws_lambda_function.discovery_handler.arn
    backup           = aws_lambda_function.backup_handler.arn
    archival         = aws_lambda_function.archival_handler.arn
    glacier_cleanup  = aws_lambda_function.glacier_cleanup_handler.arn
    api             = aws_lambda_function.api_handler.arn
    auth            = aws_lambda_function.auth_handler.arn
    email_formatter = aws_lambda_function.email_formatter.arn
  }
}

output "lambda_role_arn" {
  description = "ARN of the Lambda execution role"
  value       = aws_iam_role.lambda_role.arn
}

# =============================================================================
# STEP FUNCTIONS
# =============================================================================

output "backup_orchestrator_arn" {
  description = "ARN of the backup orchestrator Step Function"
  value       = aws_sfn_state_machine.backup_orchestrator.arn
}

output "archival_orchestrator_arn" {
  description = "ARN of the archival orchestrator Step Function"
  value       = aws_sfn_state_machine.archival_orchestrator.arn
}

# =============================================================================
# DATABASE & MONITORING
# =============================================================================

output "dynamodb_tables" {
  description = "Names of DynamoDB tables"
  value = {
    events              = aws_dynamodb_table.backup_events.name
    repository_history  = aws_dynamodb_table.repository_history.name
    download_operations = aws_dynamodb_table.download_operations.name
    glacier_jobs       = aws_dynamodb_table.glacier_jobs.name
  }
}

output "sns_topic_arn" {
  description = "ARN of the SNS topic for notifications"
  value       = aws_sns_topic.backup_notifications.arn
}

# =============================================================================
# DEPLOYMENT SUMMARY
# =============================================================================

output "deployment_summary" {
  description = "Summary of deployed resources for quick reference"
  value = {
    "🌐 Web Interface"     = "https://${var.custom_domain}"
    "📡 API Endpoint"      = "https://${aws_api_gateway_rest_api.backup_api.id}.execute-api.${data.aws_region.current.id}.amazonaws.com/${aws_api_gateway_stage.backup_api_stage.stage_name}"
    "🪣 Backup Bucket"     = aws_s3_bucket.backup_bucket.bucket
    "🧊 Glacier Vault"     = aws_glacier_vault.backup_vault.name
    "👤 Admin Username"    = "admin"
    "🌍 Environment"       = var.environment
    "📍 Region"           = data.aws_region.current.id
    "📊 CloudFront ID"    = aws_cloudfront_distribution.web_distribution.id
  }
}
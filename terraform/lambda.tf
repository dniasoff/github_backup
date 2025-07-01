# Use a public AWS Lambda Layer for Git
# This is a well-maintained public layer that includes Git and all dependencies
locals {
  git_layer_arn = "arn:aws:lambda:${data.aws_region.current.id}:553035198032:layer:git-lambda2:8"
}

# Create build directories and install dependencies
resource "null_resource" "lambda_dependencies" {
  provisioner "local-exec" {
    command = "mkdir -p ${path.module}/../build/lambda ${path.module}/../build/web && cp -r ${path.module}/../src/* ${path.module}/../build/lambda/ && cd ${path.module}/../build/lambda && pip install -r requirements.txt -t ."
  }
  
  triggers = {
    requirements = filemd5("${path.module}/../src/requirements.txt")
    source_code = join(",", [for f in fileset("${path.module}/../src", "*.py") : filemd5("${path.module}/../src/${f}")])
  }
}

# Lambda function package
data "archive_file" "lambda_zip" {
  type        = "zip"
  source_dir  = "${path.module}/../build/lambda"
  output_path = "${path.module}/../build/lambda_function.zip"
  
  depends_on = [null_resource.lambda_dependencies]
}

# Discovery Lambda Function - Optimized for cost
resource "aws_lambda_function" "discovery_handler" {
  filename         = data.archive_file.lambda_zip.output_path
  function_name    = "github-backup-discovery"
  role            = aws_iam_role.lambda_role.arn
  handler         = "discovery_handler.lambda_handler"
  source_code_hash = data.archive_file.lambda_zip.output_base64sha256
  runtime         = "python3.11"
  timeout         = 300  # 5 minutes, reduced from 15 for discovery
  memory_size     = 128  # Minimal memory for API calls only

  environment {
    variables = {
      GITHUB_ORG              = var.github_org
      GITHUB_TOKEN_SECRET_ARN = local.github_token_secret_arn
      S3_BUCKET_NAME          = aws_s3_bucket.backup_bucket.bucket
      SNS_TOPIC_ARN           = aws_sns_topic.backup_notifications.arn
    }
  }

  depends_on = [
    aws_iam_role_policy_attachment.lambda_basic_execution,
    aws_cloudwatch_log_group.discovery_log_group,
  ]
}

# Backup Lambda Function - Optimized for Git operations
resource "aws_lambda_function" "backup_handler" {
  filename         = data.archive_file.lambda_zip.output_path
  function_name    = "github-backup-nightly"
  role            = aws_iam_role.lambda_role.arn
  handler         = "backup_handler.lambda_handler"
  source_code_hash = data.archive_file.lambda_zip.output_base64sha256
  runtime         = "python3.11"
  timeout         = var.lambda_timeout_backup  # Dedicated timeout for backup operations
  memory_size     = var.lambda_memory_size_backup  # More memory for Git clone + compression
  
  # Add Git layer for complete repository cloning
  layers = [local.git_layer_arn]

  # Ephemeral storage for large Git repositories
  ephemeral_storage {
    size = 10240  # Maximum 10GB for large repositories
  }

  environment {
    variables = {
      GITHUB_ORG              = var.github_org
      GITHUB_TOKEN_SECRET_ARN = local.github_token_secret_arn
      S3_BUCKET_NAME          = aws_s3_bucket.backup_bucket.bucket
      SNS_TOPIC_ARN           = aws_sns_topic.backup_notifications.arn
      PATH                    = "/opt/bin:/usr/local/bin:/usr/bin:/bin"
    }
  }

  depends_on = [
    aws_iam_role_policy_attachment.lambda_basic_execution,
    aws_cloudwatch_log_group.backup_log_group,
  ]
}

# Archival Lambda Function - Optimized for file operations
resource "aws_lambda_function" "archival_handler" {
  filename         = data.archive_file.lambda_zip.output_path
  function_name    = "github-backup-archival"
  role            = aws_iam_role.lambda_role.arn
  handler         = "archival_handler.lambda_handler"
  source_code_hash = data.archive_file.lambda_zip.output_base64sha256
  runtime         = "python3.11"
  timeout         = 600  # 10 minutes for archival operations
  memory_size     = 256  # Reduced memory for S3/Glacier API operations

  environment {
    variables = {
      S3_BUCKET_NAME      = aws_s3_bucket.backup_bucket.bucket
      GLACIER_VAULT_NAME  = aws_glacier_vault.backup_vault.name
      RETENTION_DAYS      = var.retention_days
      SNS_TOPIC_ARN       = aws_sns_topic.backup_notifications.arn
    }
  }

  depends_on = [
    aws_iam_role_policy_attachment.lambda_basic_execution,
    aws_cloudwatch_log_group.archival_log_group,
  ]
}

# Lambda permissions for EventBridge
resource "aws_lambda_permission" "allow_eventbridge_nightly" {
  statement_id  = "AllowExecutionFromEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.backup_handler.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.nightly_backup_schedule.arn
}

resource "aws_lambda_permission" "allow_eventbridge_monthly" {
  statement_id  = "AllowExecutionFromEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.archival_handler.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.monthly_archive_schedule.arn
}

# Glacier Cleanup Lambda Function - Optimized for batch operations
resource "aws_lambda_function" "glacier_cleanup_handler" {
  filename         = data.archive_file.lambda_zip.output_path
  function_name    = "github-backup-glacier-cleanup"
  role            = aws_iam_role.lambda_role.arn
  handler         = "glacier_cleanup_handler.lambda_handler"
  source_code_hash = data.archive_file.lambda_zip.output_base64sha256
  runtime         = "python3.11"
  timeout         = 600  # 10 minutes for cleanup operations
  memory_size     = 128  # Minimal memory for API operations

  environment {
    variables = {
      S3_BUCKET_NAME         = aws_s3_bucket.backup_bucket.bucket
      GLACIER_VAULT_NAME     = aws_glacier_vault.backup_vault.name
      GLACIER_RETENTION_YEARS = var.glacier_retention_years
      SNS_TOPIC_ARN          = aws_sns_topic.backup_notifications.arn
    }
  }

  depends_on = [
    aws_iam_role_policy_attachment.lambda_basic_execution,
    aws_cloudwatch_log_group.glacier_cleanup_log_group,
  ]
}

# Email Formatter Lambda Function - Formats backup results into beautiful emails
resource "aws_lambda_function" "email_formatter" {
  filename         = data.archive_file.lambda_zip.output_path
  function_name    = "github-backup-email-formatter"
  role            = aws_iam_role.lambda_role.arn
  handler         = "email_formatter.lambda_handler"
  source_code_hash = data.archive_file.lambda_zip.output_base64sha256
  runtime         = "python3.11"
  timeout         = 60  # 1 minute for email formatting
  memory_size     = 128  # Minimal memory for formatting

  environment {
    variables = {
      SNS_TOPIC_ARN = aws_sns_topic.backup_notifications.arn
    }
  }

  depends_on = [
    aws_iam_role_policy_attachment.lambda_basic_execution,
    aws_cloudwatch_log_group.email_formatter_log_group,
  ]

  tags = {
    Name = "github-backup-email-formatter"
  }
}

# Authentication Lambda Function - Handles login and token validation
resource "aws_lambda_function" "auth_handler" {
  filename         = data.archive_file.lambda_zip.output_path
  function_name    = "github-backup-auth"
  role            = aws_iam_role.lambda_role.arn
  handler         = "auth_handler.lambda_handler"
  source_code_hash = data.archive_file.lambda_zip.output_base64sha256
  runtime         = "python3.11"
  timeout         = 30  # 30 seconds for auth operations
  memory_size     = 128  # Minimal memory for auth

  environment {
    variables = {
      AUTH_SECRET_ARN = aws_secretsmanager_secret.backup_auth.arn
      JWT_SECRET_ARN  = aws_secretsmanager_secret.jwt_secret.arn
    }
  }

  depends_on = [
    aws_iam_role_policy_attachment.lambda_basic_execution,
    aws_cloudwatch_log_group.auth_log_group,
  ]

  tags = {
    Name = "github-backup-auth"
  }
}

resource "aws_lambda_permission" "allow_eventbridge_discovery" {
  statement_id  = "AllowExecutionFromEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.discovery_handler.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.discovery_schedule.arn
}

resource "aws_lambda_permission" "allow_eventbridge_glacier_cleanup" {
  statement_id  = "AllowExecutionFromEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.glacier_cleanup_handler.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.glacier_cleanup_schedule.arn
}
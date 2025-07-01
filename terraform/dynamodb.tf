# DynamoDB Tables for Audit Trail and Backup Management

# Main audit events table - tracks all backup and download operations
resource "aws_dynamodb_table" "backup_events" {
  name           = "github-backup-events"
  billing_mode   = "PAY_PER_REQUEST"  # On-demand pricing for variable workloads
  hash_key       = "event_id"
  range_key      = "timestamp"

  attribute {
    name = "event_id"
    type = "S"  # String: UUID for each event
  }

  attribute {
    name = "timestamp"
    type = "S"  # String: ISO 8601 timestamp
  }

  attribute {
    name = "repository_name"
    type = "S"  # String: Repository name for GSI
  }

  attribute {
    name = "event_type"
    type = "S"  # String: backup, download, archival, discovery
  }

  attribute {
    name = "date_partition"
    type = "S"  # String: YYYY-MM-DD for efficient date queries
  }

  # Global Secondary Index for querying by repository
  global_secondary_index {
    name            = "RepositoryIndex"
    hash_key        = "repository_name"
    range_key       = "timestamp"
    projection_type = "ALL"
  }

  # Global Secondary Index for querying by event type
  global_secondary_index {
    name            = "EventTypeIndex"
    hash_key        = "event_type"
    range_key       = "timestamp"
    projection_type = "ALL"
  }

  # Global Secondary Index for efficient date-based queries
  global_secondary_index {
    name            = "DateIndex"
    hash_key        = "date_partition"
    range_key       = "timestamp"
    projection_type = "ALL"
  }

  tags = {
    Name = "github-backup-events"
    Purpose = "audit-trail"
  }
}

# Repository metadata and backup history table
resource "aws_dynamodb_table" "repository_history" {
  name           = "github-backup-repository-history"
  billing_mode   = "PAY_PER_REQUEST"
  hash_key       = "repository_name"
  range_key      = "backup_version"

  attribute {
    name = "repository_name"
    type = "S"  # String: Repository name
  }

  attribute {
    name = "backup_version"
    type = "S"  # String: timestamp or version identifier
  }

  attribute {
    name = "storage_class"
    type = "S"  # String: s3, glacier, deep-archive
  }

  # Global Secondary Index for querying by storage class
  global_secondary_index {
    name            = "StorageClassIndex"
    hash_key        = "storage_class"
    range_key       = "backup_version"
    projection_type = "ALL"
  }

  tags = {
    Name = "github-backup-repository-history"
    Purpose = "backup-metadata"
  }
}

# Download operations tracking table
resource "aws_dynamodb_table" "download_operations" {
  name           = "github-backup-download-operations"
  billing_mode   = "PAY_PER_REQUEST"
  hash_key       = "download_id"

  attribute {
    name = "download_id"
    type = "S"  # String: UUID for each download operation
  }

  attribute {
    name = "user_id"
    type = "S"  # String: User who initiated download
  }

  attribute {
    name = "status"
    type = "S"  # String: requested, in_progress, completed, failed
  }

  attribute {
    name = "repository_name"
    type = "S"  # String: Repository name for filtering downloads
  }

  # Global Secondary Index for querying by user
  global_secondary_index {
    name            = "UserIndex"
    hash_key        = "user_id"
    range_key       = "download_id"
    projection_type = "ALL"
  }

  # Global Secondary Index for querying by status
  global_secondary_index {
    name            = "StatusIndex"
    hash_key        = "status"
    range_key       = "download_id"
    projection_type = "ALL"
  }

  # Global Secondary Index for querying by repository
  global_secondary_index {
    name            = "RepositoryIndex"
    hash_key        = "repository_name"
    range_key       = "download_id"
    projection_type = "ALL"
  }

  # TTL attribute for automatic cleanup of old download records
  ttl {
    attribute_name = "expires_at"
    enabled        = true
  }

  tags = {
    Name = "github-backup-download-operations"
    Purpose = "download-tracking"
  }
}

# Glacier retrieval jobs tracking table
resource "aws_dynamodb_table" "glacier_jobs" {
  name           = "github-backup-glacier-jobs"
  billing_mode   = "PAY_PER_REQUEST"
  hash_key       = "job_id"

  attribute {
    name = "job_id"
    type = "S"  # String: AWS Glacier Job ID
  }

  attribute {
    name = "repository_name"
    type = "S"  # String: Repository being downloaded
  }

  attribute {
    name = "status"
    type = "S"  # String: InProgress, Succeeded, Failed
  }

  # Global Secondary Index for querying by repository
  global_secondary_index {
    name            = "RepositoryIndex"
    hash_key        = "repository_name"
    range_key       = "job_id"
    projection_type = "ALL"
  }

  # Global Secondary Index for querying by status
  global_secondary_index {
    name            = "StatusIndex"
    hash_key        = "status"
    range_key       = "job_id"
    projection_type = "ALL"
  }

  # TTL for automatic cleanup after 30 days
  ttl {
    attribute_name = "expires_at"
    enabled        = true
  }

  tags = {
    Name = "github-backup-glacier-jobs"
    Purpose = "glacier-tracking"
  }
}

# IAM role for DynamoDB access from Lambda functions
resource "aws_iam_role_policy" "lambda_dynamodb_policy" {
  name = "github-backup-lambda-dynamodb-policy"
  role = aws_iam_role.lambda_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "dynamodb:PutItem",
          "dynamodb:GetItem",
          "dynamodb:UpdateItem",
          "dynamodb:DeleteItem",
          "dynamodb:Query",
          "dynamodb:Scan",
          "dynamodb:BatchGetItem",
          "dynamodb:BatchWriteItem"
        ]
        Resource = [
          aws_dynamodb_table.backup_events.arn,
          "${aws_dynamodb_table.backup_events.arn}/index/*",
          aws_dynamodb_table.repository_history.arn,
          "${aws_dynamodb_table.repository_history.arn}/index/*",
          aws_dynamodb_table.download_operations.arn,
          "${aws_dynamodb_table.download_operations.arn}/index/*",
          aws_dynamodb_table.glacier_jobs.arn,
          "${aws_dynamodb_table.glacier_jobs.arn}/index/*"
        ]
      }
    ]
  })
}
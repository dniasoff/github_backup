# CloudWatch Log Groups
resource "aws_cloudwatch_log_group" "discovery_log_group" {
  name              = "/aws/lambda/github-backup-discovery"
  retention_in_days = 7  # Reduced for cost optimization
}

resource "aws_cloudwatch_log_group" "backup_log_group" {
  name              = "/aws/lambda/github-backup-nightly"
  retention_in_days = 14  # Keep longer for backup troubleshooting
}

resource "aws_cloudwatch_log_group" "archival_log_group" {
  name              = "/aws/lambda/github-backup-archival"
  retention_in_days = 7  # Reduced for cost optimization
}

resource "aws_cloudwatch_log_group" "glacier_cleanup_log_group" {
  name              = "/aws/lambda/github-backup-glacier-cleanup"
  retention_in_days = 7  # Reduced for cost optimization
}

resource "aws_cloudwatch_log_group" "email_formatter_log_group" {
  name              = "/aws/lambda/github-backup-email-formatter"
  retention_in_days = 3  # Very short retention for formatting logs
}

resource "aws_cloudwatch_log_group" "auth_log_group" {
  name              = "/aws/lambda/github-backup-auth"
  retention_in_days = 7  # Reduced for cost optimization
}

# EventBridge Rules for scheduling
resource "aws_cloudwatch_event_rule" "nightly_backup_schedule" {
  name                = "github-backup-nightly-schedule"
  description         = "Trigger nightly GitHub backup"
  schedule_expression = var.backup_schedule_nightly
}

resource "aws_cloudwatch_event_rule" "monthly_archive_schedule" {
  name                = "github-backup-monthly-schedule"
  description         = "Trigger monthly GitHub archive"
  schedule_expression = var.backup_schedule_monthly
}

resource "aws_cloudwatch_event_rule" "discovery_schedule" {
  name                = "github-backup-discovery-schedule"
  description         = "Trigger GitHub repository discovery"
  schedule_expression = "cron(0 1 * * ? *)"  # Daily at 1 AM
}

resource "aws_cloudwatch_event_rule" "glacier_cleanup_schedule" {
  name                = "github-backup-glacier-cleanup-schedule"
  description         = "Trigger Glacier archive cleanup (2-year retention)"
  schedule_expression = "cron(0 4 1 * ? *)"  # Monthly at 4 AM on the 1st
}

# EventBridge Targets - Updated to trigger Step Functions
resource "aws_cloudwatch_event_target" "nightly_backup_target" {
  rule      = aws_cloudwatch_event_rule.nightly_backup_schedule.name
  target_id = "GitHubBackupNightlyTarget"
  arn       = aws_sfn_state_machine.backup_orchestrator.arn
  role_arn  = aws_iam_role.eventbridge_stepfunctions_role.arn
}

resource "aws_cloudwatch_event_target" "monthly_archive_target" {
  rule      = aws_cloudwatch_event_rule.monthly_archive_schedule.name
  target_id = "GitHubBackupMonthlyTarget"
  arn       = aws_sfn_state_machine.archival_orchestrator.arn
  role_arn  = aws_iam_role.eventbridge_stepfunctions_role.arn
}

# Keep discovery as direct Lambda invocation since it's just listing repos
resource "aws_cloudwatch_event_target" "discovery_target" {
  rule      = aws_cloudwatch_event_rule.discovery_schedule.name
  target_id = "GitHubBackupDiscoveryTarget"
  arn       = aws_lambda_function.discovery_handler.arn
}

# Glacier cleanup target
resource "aws_cloudwatch_event_target" "glacier_cleanup_target" {
  rule      = aws_cloudwatch_event_rule.glacier_cleanup_schedule.name
  target_id = "GitHubBackupGlacierCleanupTarget"
  arn       = aws_lambda_function.glacier_cleanup_handler.arn
}

# IAM role for EventBridge to execute Step Functions
resource "aws_iam_role" "eventbridge_stepfunctions_role" {
  name = "github-backup-eventbridge-stepfunctions-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "events.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_role_policy" "eventbridge_stepfunctions_policy" {
  name = "github-backup-eventbridge-stepfunctions-policy"
  role = aws_iam_role.eventbridge_stepfunctions_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "states:StartExecution"
        ]
        Resource = [
          aws_sfn_state_machine.backup_orchestrator.arn,
          aws_sfn_state_machine.archival_orchestrator.arn
        ]
      }
    ]
  })
}
# Step Functions state machine for parallel backup processing
resource "aws_sfn_state_machine" "backup_orchestrator" {
  name     = "github-backup-orchestrator"
  role_arn = aws_iam_role.stepfunctions_role.arn

  definition = jsonencode({
    Comment = "GitHub Backup Orchestrator - Parallel Processing"
    StartAt = "DiscoverRepositories"
    States = {
      DiscoverRepositories = {
        Type     = "Task"
        Resource = aws_lambda_function.discovery_handler.arn
        Next     = "ParseDiscoveryResult"
        Retry = [{
          ErrorEquals = ["Lambda.ServiceException", "Lambda.AWSLambdaException", "Lambda.SdkClientException"]
          IntervalSeconds = 2
          MaxAttempts = 6
          BackoffRate = 2
        }]
      }
      ParseDiscoveryResult = {
        Type = "Pass"
        Parameters = {
          "parsed_body.$" = "States.StringToJson($.body)"
          "statusCode.$" = "$.statusCode"
        }
        Next = "ExtractRepositories"
      }
      ExtractRepositories = {
        Type = "Pass"
        Parameters = {
          "repositories.$" = "$.parsed_body.repositories"
          "statusCode.$" = "$.statusCode"
        }
        Next = "CheckRepositories"
      }
      CheckRepositories = {
        Type = "Choice"
        Choices = [{
          Variable = "$.repositories"
          IsPresent = true
          Next = "BackupRepositories"
        }]
        Default = "NoRepositories"
      }
      NoRepositories = {
        Type = "Succeed"
      }
      BackupRepositories = {
        Type = "Map"
        ItemsPath = "$.repositories"
        MaxConcurrency = 10
        Iterator = {
          StartAt = "BackupSingleRepository"
          States = {
            BackupSingleRepository = {
              Type = "Task"
              Resource = aws_lambda_function.backup_handler.arn
              End = true
              Retry = [{
                ErrorEquals = ["Lambda.ServiceException", "Lambda.AWSLambdaException", "Lambda.SdkClientException"]
                IntervalSeconds = 2
                MaxAttempts = 3
                BackoffRate = 2
              }]
              Catch = [{
                ErrorEquals = ["States.TaskFailed"]
                Next = "BackupFailed"
                ResultPath = "$.error"
              }]
            }
            BackupFailed = {
              Type = "Pass"
              Parameters = {
                "success" = false
                "error" = "Backup failed"
              }
              End = true
            }
          }
        }
        Next = "CreateSummary"
      }
      CreateSummary = {
        Type = "Pass"
        Parameters = {
          "backup_date.$" = "$$.Execution.StartTime"
          "results.$" = "$"
          "total_repositories.$" = "States.ArrayLength($)"
          "successful_backups.$" = "States.ArrayLength($[?(@.success==true)])"
        }
        Next = "SendNotification"
      }
      SendNotification = {
        Type = "Task"
        Resource = aws_lambda_function.email_formatter.arn
        End = true
        Retry = [{
          ErrorEquals = ["Lambda.ServiceException", "Lambda.AWSLambdaException", "Lambda.SdkClientException"]
          IntervalSeconds = 2
          MaxAttempts = 3
          BackoffRate = 2
        }]
      }
    }
  })

  logging_configuration {
    log_destination        = "${aws_cloudwatch_log_group.stepfunctions_log_group.arn}:*"
    include_execution_data = true
    level                  = "ERROR"
  }

  tags = {
    Name = "github-backup-orchestrator"
  }
}

# Step Functions state machine for parallel archival processing
resource "aws_sfn_state_machine" "archival_orchestrator" {
  name     = "github-archival-orchestrator"
  role_arn = aws_iam_role.stepfunctions_role.arn

  definition = jsonencode({
    Comment = "GitHub Archival Orchestrator - Parallel Processing"
    StartAt = "ListBackupsToArchive"
    States = {
      ListBackupsToArchive = {
        Type = "Task"
        Resource = aws_lambda_function.archival_handler.arn
        Parameters = {
          action = "list"
        }
        Next = "CheckBackups"
        Retry = [{
          ErrorEquals = ["Lambda.ServiceException", "Lambda.AWSLambdaException", "Lambda.SdkClientException"]
          IntervalSeconds = 2
          MaxAttempts = 6
          BackoffRate = 2
        }]
      }
      CheckBackups = {
        Type = "Choice"
        Choices = [{
          Variable = "$.backups"
          IsPresent = true
          Next = "ArchiveBackups"
        }]
        Default = "NoBackups"
      }
      NoBackups = {
        Type = "Succeed"
      }
      ArchiveBackups = {
        Type = "Map"
        ItemsPath = "$.backups"
        MaxConcurrency = 5
        Iterator = {
          StartAt = "ArchiveSingleBackup"
          States = {
            ArchiveSingleBackup = {
              Type = "Task"
              Resource = aws_lambda_function.archival_handler.arn
              Parameters = {
                "action" = "archive"
                "backup.$" = "$"
              }
              End = true
              Retry = [{
                ErrorEquals = ["Lambda.ServiceException", "Lambda.AWSLambdaException", "Lambda.SdkClientException"]
                IntervalSeconds = 5
                MaxAttempts = 3
                BackoffRate = 2
              }]
              Catch = [{
                ErrorEquals = ["States.TaskFailed"]
                Next = "ArchivalFailed"
                ResultPath = "$.error"
              }]
            }
            ArchivalFailed = {
              Type = "Pass"
              Parameters = {
                "success" = false
                "error" = "Archival failed"
              }
              End = true
            }
          }
        }
        Next = "CreateArchivalSummary"
      }
      CreateArchivalSummary = {
        Type = "Pass"
        Parameters = {
          "archival_date.$" = "$$.Execution.StartTime"
          "results.$" = "$"
          "total_backups.$" = "States.ArrayLength($)"
          "successful_archival.$" = "States.ArrayLength($[?(@.success==true)])"
        }
        Next = "SendArchivalNotification"
      }
      SendArchivalNotification = {
        Type = "Task"
        Resource = aws_lambda_function.email_formatter.arn
        End = true
        Retry = [{
          ErrorEquals = ["Lambda.ServiceException", "Lambda.AWSLambdaException", "Lambda.SdkClientException"]
          IntervalSeconds = 2
          MaxAttempts = 3
          BackoffRate = 2
        }]
      }
    }
  })

  logging_configuration {
    log_destination        = "${aws_cloudwatch_log_group.stepfunctions_archival_log_group.arn}:*"
    include_execution_data = true
    level                  = "ERROR"
  }

  tags = {
    Name = "github-archival-orchestrator"
  }
}

# IAM role for Step Functions
resource "aws_iam_role" "stepfunctions_role" {
  name = "github-backup-stepfunctions-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "states.amazonaws.com"
        }
      }
    ]
  })
}

# IAM policy for Step Functions
resource "aws_iam_role_policy" "stepfunctions_policy" {
  name = "github-backup-stepfunctions-policy"
  role = aws_iam_role.stepfunctions_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "lambda:InvokeFunction"
        ]
        Resource = [
          aws_lambda_function.discovery_handler.arn,
          aws_lambda_function.backup_handler.arn,
          aws_lambda_function.archival_handler.arn,
          aws_lambda_function.email_formatter.arn
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "sns:Publish"
        ]
        Resource = aws_sns_topic.backup_notifications.arn
      },
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogDelivery",
          "logs:GetLogDelivery",
          "logs:UpdateLogDelivery",
          "logs:DeleteLogDelivery",
          "logs:ListLogDeliveries",
          "logs:PutResourcePolicy",
          "logs:DescribeResourcePolicies",
          "logs:DescribeLogGroups"
        ]
        Resource = "*"
      }
    ]
  })
}

# CloudWatch Log Groups for Step Functions
resource "aws_cloudwatch_log_group" "stepfunctions_log_group" {
  name              = "/aws/stepfunctions/github-backup-orchestrator"
  retention_in_days = 14
}

resource "aws_cloudwatch_log_group" "stepfunctions_archival_log_group" {
  name              = "/aws/stepfunctions/github-archival-orchestrator"
  retention_in_days = 14
}
# =============================================================================
# ENVIRONMENT & REGION
# =============================================================================

variable "aws_region" {
  description = "AWS region for resources"
  type        = string
  default     = "eu-west-2"
  
  validation {
    condition     = can(regex("^[a-z0-9-]+$", var.aws_region))
    error_message = "AWS region must be a valid region identifier."
  }
}

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
  default     = "prod"
  
  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "Environment must be one of: dev, staging, prod."
  }
}

# =============================================================================
# GITHUB CONFIGURATION
# =============================================================================

variable "github_org" {
  description = "GitHub organization name to backup"
  type        = string
  default     = "QumulusTechnology"
  
  validation {
    condition     = length(var.github_org) > 0
    error_message = "GitHub organization name cannot be empty."
  }
}

variable "vault_token_path" {
  description = "Vault path to GitHub token"
  type        = string
  default     = "qcp/global/automation-user-github-token"
}

# =============================================================================
# STORAGE CONFIGURATION
# =============================================================================

variable "s3_bucket_name" {
  description = "S3 bucket name for backup storage"
  type        = string
  default     = "qumulus-github-backup-bucket"
  
  validation {
    condition     = can(regex("^[a-z0-9.-]+$", var.s3_bucket_name))
    error_message = "S3 bucket name must only contain lowercase letters, numbers, dots, and hyphens."
  }
}

variable "glacier_vault_name" {
  description = "AWS Glacier vault name for monthly archives"
  type        = string
  default     = "qumulus-github-backup-vault"
  
  validation {
    condition     = can(regex("^[a-zA-Z0-9._-]+$", var.glacier_vault_name))
    error_message = "Glacier vault name must only contain letters, numbers, dots, underscores, and hyphens."
  }
}

variable "retention_days" {
  description = "Number of days to retain nightly backups"
  type        = number
  default     = 30
  
  validation {
    condition     = var.retention_days > 0 && var.retention_days <= 365
    error_message = "Retention days must be between 1 and 365."
  }
}

variable "glacier_retention_years" {
  description = "Number of years to retain archives in Glacier before automatic deletion"
  type        = number
  default     = 2
  
  validation {
    condition     = var.glacier_retention_years > 0 && var.glacier_retention_years <= 10
    error_message = "Glacier retention years must be between 1 and 10."
  }
}

# =============================================================================
# SCHEDULING CONFIGURATION
# =============================================================================

variable "backup_schedule_nightly" {
  description = "Cron expression for nightly backups (UTC)"
  type        = string
  default     = "cron(0 2 * * ? *)"  # 2 AM UTC daily
  
  validation {
    condition     = can(regex("^cron\\(.*\\)$", var.backup_schedule_nightly))
    error_message = "Backup schedule must be a valid cron expression in AWS format."
  }
}

variable "backup_schedule_monthly" {
  description = "Cron expression for monthly archival (UTC)"
  type        = string
  default     = "cron(0 3 1 * ? *)"  # 3 AM UTC on 1st of month
  
  validation {
    condition     = can(regex("^cron\\(.*\\)$", var.backup_schedule_monthly))
    error_message = "Monthly schedule must be a valid cron expression in AWS format."
  }
}

# =============================================================================
# LAMBDA CONFIGURATION
# =============================================================================

variable "lambda_timeout" {
  description = "Default Lambda function timeout in seconds"
  type        = number
  default     = 900
  
  validation {
    condition     = var.lambda_timeout >= 1 && var.lambda_timeout <= 900
    error_message = "Lambda timeout must be between 1 and 900 seconds."
  }
}

variable "lambda_memory_size" {
  description = "Default Lambda function memory size in MB"
  type        = number
  default     = 512
  
  validation {
    condition     = var.lambda_memory_size >= 128 && var.lambda_memory_size <= 10240
    error_message = "Lambda memory size must be between 128 and 10240 MB."
  }
}

variable "lambda_memory_size_backup" {
  description = "Lambda function memory size for backup handler (uses ephemeral storage for Git operations)"
  type        = number
  default     = 1024
  
  validation {
    condition     = var.lambda_memory_size_backup >= 512 && var.lambda_memory_size_backup <= 10240
    error_message = "Backup Lambda memory size must be between 512 and 10240 MB."
  }
}

variable "lambda_timeout_backup" {
  description = "Lambda function timeout for backup operations (needs more time for Git clone)"
  type        = number
  default     = 900
  
  validation {
    condition     = var.lambda_timeout_backup >= 300 && var.lambda_timeout_backup <= 900
    error_message = "Backup Lambda timeout must be between 300 and 900 seconds."
  }
}

# =============================================================================
# WEB INTERFACE & DNS
# =============================================================================

variable "custom_domain" {
  description = "Custom domain for the web interface"
  type        = string
  default     = "github-backups.cloudportal.app"
  
  validation {
    condition     = can(regex("^[a-z0-9.-]+\\.[a-z]{2,}$", var.custom_domain))
    error_message = "Custom domain must be a valid domain name."
  }
}

variable "dns_zone_name" {
  description = "DNS zone name for the custom domain (parent zone)"
  type        = string
  default     = "cloudportal.app"
  
  validation {
    condition     = can(regex("^[a-z0-9.-]+\\.[a-z]{2,}$", var.dns_zone_name))
    error_message = "DNS zone name must be a valid domain name."
  }
}

# =============================================================================
# NOTIFICATIONS
# =============================================================================

variable "notification_email" {
  description = "Email address for backup notifications"
  type        = string
  default     = "daniel@qumulus.io"
  
  validation {
    condition     = can(regex("^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$", var.notification_email))
    error_message = "Notification email must be a valid email address."
  }
}

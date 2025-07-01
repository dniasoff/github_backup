# Glacier Vault for long-term archival
resource "aws_glacier_vault" "backup_vault" {
  name = var.glacier_vault_name

  notification {
    sns_topic = aws_sns_topic.backup_notifications.arn
    events    = ["ArchiveRetrievalCompleted", "InventoryRetrievalCompleted"]
  }
}

# Glacier Vault Lock Policy for 1 year minimum retention
resource "aws_glacier_vault_lock" "backup_vault_lock" {
  vault_name = aws_glacier_vault.backup_vault.name
  complete_lock = true

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "DenyDeleteBefore1Year"
        Effect    = "Deny"
        Principal = "*"
        Action    = [
          "glacier:DeleteArchive"
        ]
        Resource = aws_glacier_vault.backup_vault.arn
        Condition = {
          DateLessThan = {
            "glacier:ArchiveAgeInDays" = "365"
          }
        }
      }
    ]
  })
}

# Note: Glacier vault notifications are configured via the vault resource above
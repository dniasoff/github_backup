# SNS Topic for notifications
resource "aws_sns_topic" "backup_notifications" {
  name = "github-backup-notifications"
}

# Email subscription for notifications
resource "aws_sns_topic_subscription" "email_notification" {
  topic_arn = aws_sns_topic.backup_notifications.arn
  protocol  = "email"
  endpoint  = var.notification_email
}
ephemeral "vault_kv_secret_v2" "github_token" {
  mount = "secret"
  name = var.vault_token_path
}

# Create the secret in AWS Secrets Manager
resource "aws_secretsmanager_secret" "github_token" {
  name        = "github-backup/token"
  description = "GitHub token for backup operations"
  
  tags = {
    Project = "github-backup"
  }
}

# Use null_resource to store ephemeral token via AWS CLI (doesn't persist in state)
resource "null_resource" "store_github_token" {
  provisioner "local-exec" {
    command = <<-EOT
      AWS_PROFILE=vault aws secretsmanager put-secret-value \
        --secret-id ${aws_secretsmanager_secret.github_token.arn} \
        --secret-string '{"token":"${ephemeral.vault_kv_secret_v2.github_token.data["token"]}"}'
    EOT
  }
  
  # Trigger on changes to the secret
  triggers = {
    secret_arn = aws_secretsmanager_secret.github_token.arn
  }
}

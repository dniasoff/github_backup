# Authentication configuration for GitHub Backup UI

# Generate a random password for the admin user
resource "random_password" "admin_password" {
  length  = 32
  special = true
}

# Store auth credentials in AWS Secrets Manager only (no Vault dependency)
resource "aws_secretsmanager_secret" "backup_auth" {
  name        = "github-backup/auth"
  description = "Authentication credentials for GitHub backup UI"
  
  tags = {
    Name = "github-backup-auth"
  }
}

resource "aws_secretsmanager_secret_version" "backup_auth" {
  secret_id = aws_secretsmanager_secret.backup_auth.id
  
  secret_string = jsonencode({
    username = "admin"
    password = random_password.admin_password.result
  })
}

# JWT signing key for session tokens
resource "random_password" "jwt_secret" {
  length  = 64
  special = false  # Base64 friendly
}

# Store JWT secret in AWS Secrets Manager only (no Vault dependency)
resource "aws_secretsmanager_secret" "jwt_secret" {
  name        = "github-backup/jwt"
  description = "JWT signing secret for GitHub backup UI sessions"
  
  tags = {
    Name = "github-backup-jwt"
  }
}

resource "aws_secretsmanager_secret_version" "jwt_secret" {
  secret_id = aws_secretsmanager_secret.jwt_secret.id
  
  secret_string = jsonencode({
    jwt_secret = random_password.jwt_secret.result
  })
}

# Note: All outputs are now centralized in outputs.tf
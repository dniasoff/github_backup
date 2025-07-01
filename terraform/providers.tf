provider "aws" {
  profile = "vault"
  region  = var.aws_region

  default_tags {
    tags = {
      Project     = "github-backup"
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}

# Provider for DNS management in external AWS account
provider "aws" {
  alias   = "dns"
  profile = "qcp_prod"
  region  = var.aws_region

  default_tags {
    tags = {
      Project     = "github-backup"
      Environment = var.environment
      ManagedBy   = "terraform"
      Purpose     = "dns"
    }
  }
}

# Provider for ACM certificates (must be in us-east-1 for CloudFront)
provider "aws" {
  alias   = "us_east_1"
  profile = "vault"
  region  = "us-east-1"

  default_tags {
    tags = {
      Project     = "github-backup"
      Environment = var.environment
      ManagedBy   = "terraform"
      Purpose     = "ssl-certificates"
    }
  }
}

# Vault provider removed - using AWS Secrets Manager only

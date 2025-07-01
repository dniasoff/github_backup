terraform {
  backend "s3" {
    bucket       = "qumulus-tfstate-prod"
    key          = "github_backup/terraform.tfstate"
    region       = "eu-west-2"
    profile      = "qcp_prod"
    use_lockfile = true
    encrypt      = true
  }
}

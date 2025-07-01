# DNS Setup for GitHub Backup Web Interface

This document explains how to configure DNS for the GitHub Backup web interface using a custom domain hosted in a different AWS account.

## Overview

The DNS configuration sets up:
- Custom domain: `github-backups.cloudportal.app`
- SSL/TLS certificate via AWS Certificate Manager (ACM)
- CloudFront distribution with custom domain and SSL
- Route53 DNS records in external AWS account

## Prerequisites

1. **AWS Profiles**: Ensure you have the following AWS CLI profiles configured:
   - `vault`: For the main backup infrastructure
   - `qcp_prod`: For DNS management in the external account

2. **Domain Zone**: The domain `cloudportal.app` must be hosted in Route53 in the external AWS account

3. **Permissions**: Both AWS accounts need appropriate permissions:
   - Main account: ACM, CloudFront, Lambda, S3
   - DNS account: Route53 read/write access to the zone

## Configuration Files

### `dns.tf`
- Creates ACM certificate in us-east-1 (required for CloudFront)
- Sets up DNS validation records in external account
- Creates CloudFront distribution with custom domain and SSL
- Configures Route53 A and AAAA records pointing to CloudFront

### `variables.tf`
- `custom_domain`: The custom domain name (default: github-backups.cloudportal.app)
- `dns_zone_name`: The parent DNS zone (default: cloudportal.app)

### `providers.tf`
- `aws.dns`: Provider for DNS management using qcp_prod profile
- `aws.us_east_1`: Provider for ACM certificates (CloudFront requirement)

## Deployment Process

1. **Initialize Terraform** (if not already done):
   ```bash
   cd terraform
   terraform init
   ```

2. **Plan the deployment** to review changes:
   ```bash
   terraform plan
   ```

3. **Apply the configuration**:
   ```bash
   terraform apply
   ```

4. **Verify the deployment**:
   - Check ACM certificate validation
   - Verify CloudFront distribution status
   - Test DNS resolution: `nslookup github-backups.cloudportal.app`
   - Verify SSL certificate: `openssl s_client -connect github-backups.cloudportal.app:443`

## DNS Records Created

1. **Certificate Validation Records**: CNAME records for ACM certificate validation
2. **A Record**: `github-backups.cloudportal.app` → CloudFront distribution
3. **AAAA Record**: IPv6 support for the domain
4. **CNAME Record**: `www.github-backups.cloudportal.app` → `github-backups.cloudportal.app`

## Security Considerations

1. **SSL/TLS**: 
   - Certificate uses TLS 1.2 minimum
   - SNI-only support (modern browsers)
   - Automatic certificate renewal via ACM

2. **CloudFront Security**:
   - HTTPS redirect for all traffic
   - Gzip compression enabled
   - API endpoints have no caching for security

3. **Cross-Account Access**:
   - DNS management isolated to dedicated account
   - Minimal permissions via IAM roles

## Troubleshooting

### Certificate Validation Issues
```bash
# Check certificate status
aws acm list-certificates --region us-east-1 --profile vault

# Check DNS validation records
aws route53 list-resource-record-sets --hosted-zone-id <zone-id> --profile qcp_prod
```

### CloudFront Issues
```bash
# Check distribution status
aws cloudfront list-distributions --profile vault

# Create invalidation if needed
aws cloudfront create-invalidation --distribution-id <dist-id> --paths "/*" --profile vault
```

### DNS Resolution Issues
```bash
# Test DNS resolution
nslookup github-backups.cloudportal.app
dig github-backups.cloudportal.app

# Check from different DNS servers
nslookup github-backups.cloudportal.app 8.8.8.8
```

## Customization

To use a different domain:

1. Update variables in `terraform.tfvars`:
   ```hcl
   custom_domain = "your-domain.example.com"
   dns_zone_name = "example.com"
   ```

2. Ensure the DNS zone exists in the external account

3. Update the provider profile if using a different AWS account:
   ```hcl
   provider "aws" {
     alias   = "dns"
     profile = "your-dns-profile"
     region  = var.aws_region
   }
   ```

## Outputs

After successful deployment, the following URLs will be available:

- **Custom Domain**: `https://github-backups.cloudportal.app`
- **CloudFront URL**: `https://<distribution-id>.cloudfront.net`
- **Certificate ARN**: Used for reference and monitoring

## Maintenance

1. **Certificate Renewal**: Automatic via ACM
2. **DNS Changes**: Update Route53 records as needed
3. **CloudFront Updates**: Deploy through Terraform for consistency
4. **Monitoring**: Check CloudWatch metrics for both accounts

## Cost Implications

- **Route53**: $0.50/month per hosted zone + query charges
- **ACM Certificate**: Free for CloudFront use
- **CloudFront**: Standard data transfer and request charges
- **DNS Queries**: ~$0.40 per million queries

## Support

For DNS-related issues:
1. Check AWS CloudTrail logs in both accounts
2. Verify IAM permissions for cross-account access
3. Test DNS propagation with online tools
4. Monitor CloudWatch metrics for errors
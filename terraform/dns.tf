# DNS Configuration for github-backups.cloudportal.app
# Domain is hosted in a different AWS account using qcp_prod profile

# Data source to get the hosted zone from the external AWS account
data "aws_route53_zone" "main" {
  provider = aws.dns
  name     = var.dns_zone_name
}

# DNS A record pointing to CloudFront distribution
resource "aws_route53_record" "web_domain" {
  provider = aws.dns
  zone_id  = data.aws_route53_zone.main.zone_id
  name     = var.custom_domain
  type     = "A"

  alias {
    name                   = aws_cloudfront_distribution.web_distribution.domain_name
    zone_id                = aws_cloudfront_distribution.web_distribution.hosted_zone_id
    evaluate_target_health = false
  }
  
  depends_on = [aws_cloudfront_distribution.web_distribution]
}

# AAAA record for IPv6 support
resource "aws_route53_record" "web_domain_ipv6" {
  provider = aws.dns
  zone_id  = data.aws_route53_zone.main.zone_id
  name     = var.custom_domain
  type     = "AAAA"

  alias {
    name                   = aws_cloudfront_distribution.web_distribution.domain_name
    zone_id                = aws_cloudfront_distribution.web_distribution.hosted_zone_id
    evaluate_target_health = false
  }
  
  depends_on = [aws_cloudfront_distribution.web_distribution]
}

# CNAME for www subdomain
resource "aws_route53_record" "web_domain_www" {
  provider = aws.dns
  zone_id  = data.aws_route53_zone.main.zone_id
  name     = "www.${var.custom_domain}"
  type     = "CNAME"
  ttl      = 300
  records  = [var.custom_domain]
  
  depends_on = [aws_route53_record.web_domain]
}
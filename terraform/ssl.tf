# SSL/TLS Certificate Configuration
# ACM certificates must be in us-east-1 for CloudFront

# ACM Certificate for SSL/TLS
resource "aws_acm_certificate" "web_cert" {
  provider    = aws.us_east_1
  domain_name = var.custom_domain
  
  subject_alternative_names = [
    "www.${var.custom_domain}"
  ]
  
  validation_method = "DNS"
  
  lifecycle {
    create_before_destroy = true
  }
  
  tags = {
    Name        = "github-backups-ssl-cert"
    Domain      = var.custom_domain
    Environment = var.environment
  }
}

# Certificate validation records (created in the DNS account)
resource "aws_route53_record" "cert_validation" {
  provider = aws.dns
  
  for_each = {
    for dvo in aws_acm_certificate.web_cert.domain_validation_options : dvo.domain_name => {
      name   = dvo.resource_record_name
      record = dvo.resource_record_value
      type   = dvo.resource_record_type
    }
  }
  
  allow_overwrite = true
  name            = each.value.name
  records         = [each.value.record]
  ttl             = 60
  type            = each.value.type
  zone_id         = data.aws_route53_zone.main.zone_id
}

# Certificate validation
resource "aws_acm_certificate_validation" "web_cert" {
  provider        = aws.us_east_1
  certificate_arn = aws_acm_certificate.web_cert.arn
  
  validation_record_fqdns = [
    for record in aws_route53_record.cert_validation : record.fqdn
  ]
  
  timeouts {
    create = "5m"
  }
}
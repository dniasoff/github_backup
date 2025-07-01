# S3 bucket for hosting the web interface
resource "aws_s3_bucket" "web_hosting" {
  bucket = "${var.s3_bucket_name}-web"
  
  tags = {
    Name = "github-backup-web"
    Purpose = "web-hosting"
  }
}

# S3 bucket public access configuration
resource "aws_s3_bucket_public_access_block" "web_hosting_pab" {
  bucket = aws_s3_bucket.web_hosting.id

  block_public_acls       = false
  block_public_policy     = false
  ignore_public_acls      = false
  restrict_public_buckets = false
}

# S3 bucket policy for public read access
resource "aws_s3_bucket_policy" "web_hosting_policy" {
  bucket = aws_s3_bucket.web_hosting.id
  depends_on = [aws_s3_bucket_public_access_block.web_hosting_pab]

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "PublicReadGetObject"
        Effect    = "Allow"
        Principal = "*"
        Action    = "s3:GetObject"
        Resource  = "${aws_s3_bucket.web_hosting.arn}/*"
      }
    ]
  })
}

# S3 bucket website configuration
resource "aws_s3_bucket_website_configuration" "web_hosting_website" {
  bucket = aws_s3_bucket.web_hosting.id

  index_document {
    suffix = "index.html"
  }

  error_document {
    key = "error.html"
  }
}

# S3 Static Website Hosting Configuration
# CloudFront distribution is defined in cloudfront.tf
# SSL certificates are defined in ssl.tf

# Note: index.html is uploaded via the configured version below

# Create configured web files in build directory
resource "local_file" "configured_index" {
  content = replace(
    replace(
      file("${path.module}/../web/index.html"),
      "YOUR_API_GATEWAY_URL_HERE",
      "https://${aws_api_gateway_rest_api.backup_api.id}.execute-api.${data.aws_region.current.id}.amazonaws.com/${aws_api_gateway_stage.backup_api_stage.stage_name}"
    ),
    "YOUR_DOMAIN_HERE",
    var.custom_domain
  )
  filename = "${path.module}/../build/web/index.html"
}

resource "local_file" "configured_login" {
  content = replace(
    replace(
      file("${path.module}/../web/login.html"),
      "YOUR_API_GATEWAY_URL_HERE",
      "https://${aws_api_gateway_rest_api.backup_api.id}.execute-api.${data.aws_region.current.id}.amazonaws.com/${aws_api_gateway_stage.backup_api_stage.stage_name}"
    ),
    "YOUR_DOMAIN_HERE", 
    var.custom_domain
  )
  filename = "${path.module}/../build/web/login.html"
}

# Upload the configured web files
resource "aws_s3_object" "configured_index_html" {
  bucket       = aws_s3_bucket.web_hosting.bucket
  key          = "index.html"
  source       = local_file.configured_index.filename
  content_type = "text/html"
  etag         = local_file.configured_index.content_md5
  
  depends_on = [
    aws_s3_bucket_policy.web_hosting_policy,
    local_file.configured_index
  ]
}

resource "aws_s3_object" "configured_login_html" {
  bucket       = aws_s3_bucket.web_hosting.bucket
  key          = "login.html"
  source       = local_file.configured_login.filename
  content_type = "text/html"
  etag         = local_file.configured_login.content_md5
  
  depends_on = [
    aws_s3_bucket_policy.web_hosting_policy,
    local_file.configured_login
  ]
}

# Create a simple error page
resource "aws_s3_object" "error_html" {
  bucket       = aws_s3_bucket.web_hosting.bucket
  key          = "error.html"
  content_type = "text/html"
  
  content = <<EOF
<!DOCTYPE html>
<html>
<head>
    <title>GitHub Backup Management - Error</title>
    <style>
        body { font-family: Arial, sans-serif; text-align: center; padding: 50px; }
        h1 { color: #d32f2f; }
    </style>
</head>
<body>
    <h1>Page Not Found</h1>
    <p>The requested page could not be found.</p>
    <a href="/">Return to Home</a>
</body>
</html>
EOF
  
  depends_on = [aws_s3_bucket_policy.web_hosting_policy]
}

# Note: All outputs are now centralized in outputs.tf
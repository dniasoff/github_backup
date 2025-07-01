# API Gateway for GitHub Backup Management Interface

# REST API Gateway
resource "aws_api_gateway_rest_api" "backup_api" {
  name        = "github-backup-api"
  description = "API for GitHub backup management and download operations"
  
  endpoint_configuration {
    types = ["REGIONAL"]
  }
  
  tags = {
    Name = "github-backup-api"
  }
}

# API Gateway Deployment
resource "aws_api_gateway_deployment" "backup_api_deployment" {
  depends_on = [
    aws_api_gateway_method.repositories_get,
    aws_api_gateway_method.repository_history_get,
    aws_api_gateway_method.repository_versions_get,
    aws_api_gateway_method.repository_downloads_get,
    aws_api_gateway_method.events_get,
    aws_api_gateway_method.download_post,
    aws_api_gateway_method.download_status_get,
    aws_api_gateway_method.dashboard_get,
    aws_api_gateway_method.auth_login_post,
    aws_api_gateway_method.auth_validate_post,
    aws_api_gateway_method.auth_logout_post,
    aws_api_gateway_method.options_repositories,
    aws_api_gateway_method.options_repository_history,
    aws_api_gateway_method.options_repository_versions,
    aws_api_gateway_method.options_repository_downloads,
    aws_api_gateway_method.options_events,
    aws_api_gateway_method.options_download,
    aws_api_gateway_method.options_download_status,
    aws_api_gateway_method.options_dashboard,
    aws_api_gateway_method.options_auth_login,
    aws_api_gateway_method.options_auth_validate,
    aws_api_gateway_method.options_auth_logout
  ]
  
  rest_api_id = aws_api_gateway_rest_api.backup_api.id
  
  triggers = {
    redeployment = sha1(jsonencode([
      aws_api_gateway_resource.repositories.id,
      aws_api_gateway_method.repositories_get.id,
      aws_api_gateway_integration.repositories_get.id,
      aws_api_gateway_resource.download.id,
      aws_api_gateway_method.download_post.id,
      aws_api_gateway_integration.download_post.id,
      aws_api_gateway_method_response.download_post_200.id,
      aws_api_gateway_resource.download_status.id,
      aws_api_gateway_method.download_status_get.id,
      aws_api_gateway_integration.download_status_get.id,
      aws_api_gateway_method_response.download_status_get_200.id,
    ]))
  }
  
  lifecycle {
    create_before_destroy = true
  }
}

# API Gateway Stage
resource "aws_api_gateway_stage" "backup_api_stage" {
  deployment_id = aws_api_gateway_deployment.backup_api_deployment.id
  rest_api_id   = aws_api_gateway_rest_api.backup_api.id
  stage_name    = "prod"
}

# Lambda function for API
resource "aws_lambda_function" "api_handler" {
  filename         = data.archive_file.lambda_zip.output_path
  function_name    = "github-backup-api"
  role            = aws_iam_role.lambda_role.arn
  handler         = "api_handler.lambda_handler"
  source_code_hash = data.archive_file.lambda_zip.output_base64sha256
  runtime         = "python3.11"
  timeout         = 30
  memory_size     = 512

  environment {
    variables = {
      S3_BUCKET_NAME      = aws_s3_bucket.backup_bucket.bucket
      GLACIER_VAULT_NAME  = aws_glacier_vault.backup_vault.name
      AUTH_SECRET_ARN     = aws_secretsmanager_secret.backup_auth.arn
      JWT_SECRET_ARN      = aws_secretsmanager_secret.jwt_secret.arn
    }
  }

  depends_on = [
    aws_iam_role_policy_attachment.lambda_basic_execution,
    aws_cloudwatch_log_group.api_log_group,
  ]
  
  tags = {
    Name = "github-backup-api"
  }
}

# CloudWatch Log Group for API
resource "aws_cloudwatch_log_group" "api_log_group" {
  name              = "/aws/lambda/github-backup-api"
  retention_in_days = 14
}

# Lambda permission for API Gateway
resource "aws_lambda_permission" "allow_api_gateway" {
  statement_id  = "AllowExecutionFromAPIGateway"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.api_handler.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.backup_api.execution_arn}/*/*"
}

# Lambda permission for Auth Gateway
resource "aws_lambda_permission" "allow_auth_api_gateway" {
  statement_id  = "AllowExecutionFromAPIGateway"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.auth_handler.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.backup_api.execution_arn}/*/*"
}

# Resources and Methods

# /repositories resource
resource "aws_api_gateway_resource" "repositories" {
  rest_api_id = aws_api_gateway_rest_api.backup_api.id
  parent_id   = aws_api_gateway_rest_api.backup_api.root_resource_id
  path_part   = "repositories"
}

resource "aws_api_gateway_method" "repositories_get" {
  rest_api_id   = aws_api_gateway_rest_api.backup_api.id
  resource_id   = aws_api_gateway_resource.repositories.id
  http_method   = "GET"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "repositories_get" {
  rest_api_id             = aws_api_gateway_rest_api.backup_api.id
  resource_id             = aws_api_gateway_resource.repositories.id
  http_method             = aws_api_gateway_method.repositories_get.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.api_handler.invoke_arn
}

# /repositories/{repository} resource
resource "aws_api_gateway_resource" "repository" {
  rest_api_id = aws_api_gateway_rest_api.backup_api.id
  parent_id   = aws_api_gateway_resource.repositories.id
  path_part   = "{repository}"
}

# /repositories/{repository}/history resource
resource "aws_api_gateway_resource" "repository_history" {
  rest_api_id = aws_api_gateway_rest_api.backup_api.id
  parent_id   = aws_api_gateway_resource.repository.id
  path_part   = "history"
}

resource "aws_api_gateway_method" "repository_history_get" {
  rest_api_id   = aws_api_gateway_rest_api.backup_api.id
  resource_id   = aws_api_gateway_resource.repository_history.id
  http_method   = "GET"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "repository_history_get" {
  rest_api_id             = aws_api_gateway_rest_api.backup_api.id
  resource_id             = aws_api_gateway_resource.repository_history.id
  http_method             = aws_api_gateway_method.repository_history_get.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.api_handler.invoke_arn
}

# /repositories/{repository}/versions resource
resource "aws_api_gateway_resource" "repository_versions" {
  rest_api_id = aws_api_gateway_rest_api.backup_api.id
  parent_id   = aws_api_gateway_resource.repository.id
  path_part   = "versions"
}

resource "aws_api_gateway_method" "repository_versions_get" {
  rest_api_id   = aws_api_gateway_rest_api.backup_api.id
  resource_id   = aws_api_gateway_resource.repository_versions.id
  http_method   = "GET"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "repository_versions_get" {
  rest_api_id             = aws_api_gateway_rest_api.backup_api.id
  resource_id             = aws_api_gateway_resource.repository_versions.id
  http_method             = aws_api_gateway_method.repository_versions_get.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.api_handler.invoke_arn
}

# /repositories/{repository}/downloads resource
resource "aws_api_gateway_resource" "repository_downloads" {
  rest_api_id = aws_api_gateway_rest_api.backup_api.id
  parent_id   = aws_api_gateway_resource.repository.id
  path_part   = "downloads"
}

resource "aws_api_gateway_method" "repository_downloads_get" {
  rest_api_id   = aws_api_gateway_rest_api.backup_api.id
  resource_id   = aws_api_gateway_resource.repository_downloads.id
  http_method   = "GET"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "repository_downloads_get" {
  rest_api_id             = aws_api_gateway_rest_api.backup_api.id
  resource_id             = aws_api_gateway_resource.repository_downloads.id
  http_method             = aws_api_gateway_method.repository_downloads_get.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.api_handler.invoke_arn
}

# /events resource
resource "aws_api_gateway_resource" "events" {
  rest_api_id = aws_api_gateway_rest_api.backup_api.id
  parent_id   = aws_api_gateway_rest_api.backup_api.root_resource_id
  path_part   = "events"
}

resource "aws_api_gateway_method" "events_get" {
  rest_api_id   = aws_api_gateway_rest_api.backup_api.id
  resource_id   = aws_api_gateway_resource.events.id
  http_method   = "GET"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "events_get" {
  rest_api_id             = aws_api_gateway_rest_api.backup_api.id
  resource_id             = aws_api_gateway_resource.events.id
  http_method             = aws_api_gateway_method.events_get.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.api_handler.invoke_arn
}

# /download resource
resource "aws_api_gateway_resource" "download" {
  rest_api_id = aws_api_gateway_rest_api.backup_api.id
  parent_id   = aws_api_gateway_rest_api.backup_api.root_resource_id
  path_part   = "download"
}

resource "aws_api_gateway_method" "download_post" {
  rest_api_id   = aws_api_gateway_rest_api.backup_api.id
  resource_id   = aws_api_gateway_resource.download.id
  http_method   = "POST"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "download_post" {
  rest_api_id             = aws_api_gateway_rest_api.backup_api.id
  resource_id             = aws_api_gateway_resource.download.id
  http_method             = aws_api_gateway_method.download_post.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.api_handler.invoke_arn
  
  # Ensure proper request handling
  passthrough_behavior = "WHEN_NO_MATCH"
  content_handling     = "CONVERT_TO_TEXT"
}

# /download/{download_id} resource
resource "aws_api_gateway_resource" "download_status" {
  rest_api_id = aws_api_gateway_rest_api.backup_api.id
  parent_id   = aws_api_gateway_resource.download.id
  path_part   = "{download_id}"
}

resource "aws_api_gateway_method" "download_status_get" {
  rest_api_id   = aws_api_gateway_rest_api.backup_api.id
  resource_id   = aws_api_gateway_resource.download_status.id
  http_method   = "GET"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "download_status_get" {
  rest_api_id             = aws_api_gateway_rest_api.backup_api.id
  resource_id             = aws_api_gateway_resource.download_status.id
  http_method             = aws_api_gateway_method.download_status_get.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.api_handler.invoke_arn
  
  # Ensure proper request handling
  passthrough_behavior = "WHEN_NO_MATCH"
  content_handling     = "CONVERT_TO_TEXT"
}

# Method responses for download endpoints
resource "aws_api_gateway_method_response" "download_post_200" {
  rest_api_id = aws_api_gateway_rest_api.backup_api.id
  resource_id = aws_api_gateway_resource.download.id
  http_method = aws_api_gateway_method.download_post.http_method
  status_code = "200"
  
  response_parameters = {
    "method.response.header.Access-Control-Allow-Origin" = true
    "method.response.header.Access-Control-Allow-Headers" = true
  }
}

resource "aws_api_gateway_method_response" "download_status_get_200" {
  rest_api_id = aws_api_gateway_rest_api.backup_api.id
  resource_id = aws_api_gateway_resource.download_status.id
  http_method = aws_api_gateway_method.download_status_get.http_method
  status_code = "200"
  
  response_parameters = {
    "method.response.header.Access-Control-Allow-Origin" = true
    "method.response.header.Access-Control-Allow-Headers" = true
  }
}

# /dashboard resource
resource "aws_api_gateway_resource" "dashboard" {
  rest_api_id = aws_api_gateway_rest_api.backup_api.id
  parent_id   = aws_api_gateway_rest_api.backup_api.root_resource_id
  path_part   = "dashboard"
}

# /auth resource
resource "aws_api_gateway_resource" "auth" {
  rest_api_id = aws_api_gateway_rest_api.backup_api.id
  parent_id   = aws_api_gateway_rest_api.backup_api.root_resource_id
  path_part   = "auth"
}

# /auth/login resource
resource "aws_api_gateway_resource" "auth_login" {
  rest_api_id = aws_api_gateway_rest_api.backup_api.id
  parent_id   = aws_api_gateway_resource.auth.id
  path_part   = "login"
}

# /auth/validate resource
resource "aws_api_gateway_resource" "auth_validate" {
  rest_api_id = aws_api_gateway_rest_api.backup_api.id
  parent_id   = aws_api_gateway_resource.auth.id
  path_part   = "validate"
}

# /auth/logout resource
resource "aws_api_gateway_resource" "auth_logout" {
  rest_api_id = aws_api_gateway_rest_api.backup_api.id
  parent_id   = aws_api_gateway_resource.auth.id
  path_part   = "logout"
}

resource "aws_api_gateway_method" "dashboard_get" {
  rest_api_id   = aws_api_gateway_rest_api.backup_api.id
  resource_id   = aws_api_gateway_resource.dashboard.id
  http_method   = "GET"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "dashboard_get" {
  rest_api_id             = aws_api_gateway_rest_api.backup_api.id
  resource_id             = aws_api_gateway_resource.dashboard.id
  http_method             = aws_api_gateway_method.dashboard_get.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.api_handler.invoke_arn
}

# Auth methods
resource "aws_api_gateway_method" "auth_login_post" {
  rest_api_id   = aws_api_gateway_rest_api.backup_api.id
  resource_id   = aws_api_gateway_resource.auth_login.id
  http_method   = "POST"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "auth_login_post" {
  rest_api_id             = aws_api_gateway_rest_api.backup_api.id
  resource_id             = aws_api_gateway_resource.auth_login.id
  http_method             = aws_api_gateway_method.auth_login_post.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.auth_handler.invoke_arn
}

resource "aws_api_gateway_method" "auth_validate_post" {
  rest_api_id   = aws_api_gateway_rest_api.backup_api.id
  resource_id   = aws_api_gateway_resource.auth_validate.id
  http_method   = "POST"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "auth_validate_post" {
  rest_api_id             = aws_api_gateway_rest_api.backup_api.id
  resource_id             = aws_api_gateway_resource.auth_validate.id
  http_method             = aws_api_gateway_method.auth_validate_post.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.auth_handler.invoke_arn
}

resource "aws_api_gateway_method" "auth_logout_post" {
  rest_api_id   = aws_api_gateway_rest_api.backup_api.id
  resource_id   = aws_api_gateway_resource.auth_logout.id
  http_method   = "POST"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "auth_logout_post" {
  rest_api_id             = aws_api_gateway_rest_api.backup_api.id
  resource_id             = aws_api_gateway_resource.auth_logout.id
  http_method             = aws_api_gateway_method.auth_logout_post.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.auth_handler.invoke_arn
}

# CORS Configuration - OPTIONS methods for all resources

# OPTIONS for /repositories
resource "aws_api_gateway_method" "options_repositories" {
  rest_api_id   = aws_api_gateway_rest_api.backup_api.id
  resource_id   = aws_api_gateway_resource.repositories.id
  http_method   = "OPTIONS"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "options_repositories" {
  rest_api_id = aws_api_gateway_rest_api.backup_api.id
  resource_id = aws_api_gateway_resource.repositories.id
  http_method = aws_api_gateway_method.options_repositories.http_method
  type        = "MOCK"
  
  request_templates = {
    "application/json" = "{\"statusCode\": 200}"
  }
}

resource "aws_api_gateway_method_response" "options_repositories" {
  rest_api_id = aws_api_gateway_rest_api.backup_api.id
  resource_id = aws_api_gateway_resource.repositories.id
  http_method = aws_api_gateway_method.options_repositories.http_method
  status_code = "200"
  
  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = true
    "method.response.header.Access-Control-Allow-Methods" = true
    "method.response.header.Access-Control-Allow-Origin"  = true
  }
}

resource "aws_api_gateway_integration_response" "options_repositories" {
  rest_api_id = aws_api_gateway_rest_api.backup_api.id
  resource_id = aws_api_gateway_resource.repositories.id
  http_method = aws_api_gateway_method.options_repositories.http_method
  status_code = aws_api_gateway_method_response.options_repositories.status_code
  
  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = "'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token'"
    "method.response.header.Access-Control-Allow-Methods" = "'GET,OPTIONS'"
    "method.response.header.Access-Control-Allow-Origin"  = "'*'"
  }
}

# Similar OPTIONS methods for other resources (abbreviated for brevity)
# You would repeat the OPTIONS pattern for each resource

# OPTIONS for /repositories/{repository}/history
resource "aws_api_gateway_method" "options_repository_history" {
  rest_api_id   = aws_api_gateway_rest_api.backup_api.id
  resource_id   = aws_api_gateway_resource.repository_history.id
  http_method   = "OPTIONS"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "options_repository_history" {
  rest_api_id = aws_api_gateway_rest_api.backup_api.id
  resource_id = aws_api_gateway_resource.repository_history.id
  http_method = aws_api_gateway_method.options_repository_history.http_method
  type        = "MOCK"
  
  request_templates = {
    "application/json" = "{\"statusCode\": 200}"
  }
}

resource "aws_api_gateway_method_response" "options_repository_history" {
  rest_api_id = aws_api_gateway_rest_api.backup_api.id
  resource_id = aws_api_gateway_resource.repository_history.id
  http_method = aws_api_gateway_method.options_repository_history.http_method
  status_code = "200"
  
  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = true
    "method.response.header.Access-Control-Allow-Methods" = true
    "method.response.header.Access-Control-Allow-Origin"  = true
  }
}

resource "aws_api_gateway_integration_response" "options_repository_history" {
  rest_api_id = aws_api_gateway_rest_api.backup_api.id
  resource_id = aws_api_gateway_resource.repository_history.id
  http_method = aws_api_gateway_method.options_repository_history.http_method
  status_code = aws_api_gateway_method_response.options_repository_history.status_code
  
  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = "'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token'"
    "method.response.header.Access-Control-Allow-Methods" = "'GET,OPTIONS'"
    "method.response.header.Access-Control-Allow-Origin"  = "'*'"
  }
}

# OPTIONS for /repositories/{repository}/versions
resource "aws_api_gateway_method" "options_repository_versions" {
  rest_api_id   = aws_api_gateway_rest_api.backup_api.id
  resource_id   = aws_api_gateway_resource.repository_versions.id
  http_method   = "OPTIONS"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "options_repository_versions" {
  rest_api_id = aws_api_gateway_rest_api.backup_api.id
  resource_id = aws_api_gateway_resource.repository_versions.id
  http_method = aws_api_gateway_method.options_repository_versions.http_method
  type        = "MOCK"
  
  request_templates = {
    "application/json" = "{\"statusCode\": 200}"
  }
}

resource "aws_api_gateway_method_response" "options_repository_versions" {
  rest_api_id = aws_api_gateway_rest_api.backup_api.id
  resource_id = aws_api_gateway_resource.repository_versions.id
  http_method = aws_api_gateway_method.options_repository_versions.http_method
  status_code = "200"
  
  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = true
    "method.response.header.Access-Control-Allow-Methods" = true
    "method.response.header.Access-Control-Allow-Origin"  = true
  }
}

resource "aws_api_gateway_integration_response" "options_repository_versions" {
  rest_api_id = aws_api_gateway_rest_api.backup_api.id
  resource_id = aws_api_gateway_resource.repository_versions.id
  http_method = aws_api_gateway_method.options_repository_versions.http_method
  status_code = aws_api_gateway_method_response.options_repository_versions.status_code
  
  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = "'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token'"
    "method.response.header.Access-Control-Allow-Methods" = "'GET,OPTIONS'"
    "method.response.header.Access-Control-Allow-Origin"  = "'*'"
  }
}

# OPTIONS for /repositories/{repository}/downloads
resource "aws_api_gateway_method" "options_repository_downloads" {
  rest_api_id   = aws_api_gateway_rest_api.backup_api.id
  resource_id   = aws_api_gateway_resource.repository_downloads.id
  http_method   = "OPTIONS"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "options_repository_downloads" {
  rest_api_id = aws_api_gateway_rest_api.backup_api.id
  resource_id = aws_api_gateway_resource.repository_downloads.id
  http_method = aws_api_gateway_method.options_repository_downloads.http_method
  type        = "MOCK"
  
  request_templates = {
    "application/json" = "{\"statusCode\": 200}"
  }
}

resource "aws_api_gateway_method_response" "options_repository_downloads" {
  rest_api_id = aws_api_gateway_rest_api.backup_api.id
  resource_id = aws_api_gateway_resource.repository_downloads.id
  http_method = aws_api_gateway_method.options_repository_downloads.http_method
  status_code = "200"
  
  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = true
    "method.response.header.Access-Control-Allow-Methods" = true
    "method.response.header.Access-Control-Allow-Origin"  = true
  }
}

resource "aws_api_gateway_integration_response" "options_repository_downloads" {
  rest_api_id = aws_api_gateway_rest_api.backup_api.id
  resource_id = aws_api_gateway_resource.repository_downloads.id
  http_method = aws_api_gateway_method.options_repository_downloads.http_method
  status_code = aws_api_gateway_method_response.options_repository_downloads.status_code
  
  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = "'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token'"
    "method.response.header.Access-Control-Allow-Methods" = "'GET,OPTIONS'"
    "method.response.header.Access-Control-Allow-Origin"  = "'*'"
  }
}

# OPTIONS for /events
resource "aws_api_gateway_method" "options_events" {
  rest_api_id   = aws_api_gateway_rest_api.backup_api.id
  resource_id   = aws_api_gateway_resource.events.id
  http_method   = "OPTIONS"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "options_events" {
  rest_api_id = aws_api_gateway_rest_api.backup_api.id
  resource_id = aws_api_gateway_resource.events.id
  http_method = aws_api_gateway_method.options_events.http_method
  type        = "MOCK"
  
  request_templates = {
    "application/json" = "{\"statusCode\": 200}"
  }
}

resource "aws_api_gateway_method_response" "options_events" {
  rest_api_id = aws_api_gateway_rest_api.backup_api.id
  resource_id = aws_api_gateway_resource.events.id
  http_method = aws_api_gateway_method.options_events.http_method
  status_code = "200"
  
  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = true
    "method.response.header.Access-Control-Allow-Methods" = true
    "method.response.header.Access-Control-Allow-Origin"  = true
  }
}

resource "aws_api_gateway_integration_response" "options_events" {
  rest_api_id = aws_api_gateway_rest_api.backup_api.id
  resource_id = aws_api_gateway_resource.events.id
  http_method = aws_api_gateway_method.options_events.http_method
  status_code = aws_api_gateway_method_response.options_events.status_code
  
  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = "'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token'"
    "method.response.header.Access-Control-Allow-Methods" = "'GET,OPTIONS'"
    "method.response.header.Access-Control-Allow-Origin"  = "'*'"
  }
}

# OPTIONS for /download
resource "aws_api_gateway_method" "options_download" {
  rest_api_id   = aws_api_gateway_rest_api.backup_api.id
  resource_id   = aws_api_gateway_resource.download.id
  http_method   = "OPTIONS"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "options_download" {
  rest_api_id = aws_api_gateway_rest_api.backup_api.id
  resource_id = aws_api_gateway_resource.download.id
  http_method = aws_api_gateway_method.options_download.http_method
  type        = "MOCK"
  
  request_templates = {
    "application/json" = "{\"statusCode\": 200}"
  }
}

resource "aws_api_gateway_method_response" "options_download" {
  rest_api_id = aws_api_gateway_rest_api.backup_api.id
  resource_id = aws_api_gateway_resource.download.id
  http_method = aws_api_gateway_method.options_download.http_method
  status_code = "200"
  
  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = true
    "method.response.header.Access-Control-Allow-Methods" = true
    "method.response.header.Access-Control-Allow-Origin"  = true
  }
}

resource "aws_api_gateway_integration_response" "options_download" {
  rest_api_id = aws_api_gateway_rest_api.backup_api.id
  resource_id = aws_api_gateway_resource.download.id
  http_method = aws_api_gateway_method.options_download.http_method
  status_code = aws_api_gateway_method_response.options_download.status_code
  
  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = "'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token'"
    "method.response.header.Access-Control-Allow-Methods" = "'POST,OPTIONS'"
    "method.response.header.Access-Control-Allow-Origin"  = "'*'"
  }
}

# OPTIONS for /download/{download_id}
resource "aws_api_gateway_method" "options_download_status" {
  rest_api_id   = aws_api_gateway_rest_api.backup_api.id
  resource_id   = aws_api_gateway_resource.download_status.id
  http_method   = "OPTIONS"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "options_download_status" {
  rest_api_id = aws_api_gateway_rest_api.backup_api.id
  resource_id = aws_api_gateway_resource.download_status.id
  http_method = aws_api_gateway_method.options_download_status.http_method
  type        = "MOCK"
  
  request_templates = {
    "application/json" = "{\"statusCode\": 200}"
  }
}

resource "aws_api_gateway_method_response" "options_download_status" {
  rest_api_id = aws_api_gateway_rest_api.backup_api.id
  resource_id = aws_api_gateway_resource.download_status.id
  http_method = aws_api_gateway_method.options_download_status.http_method
  status_code = "200"
  
  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = true
    "method.response.header.Access-Control-Allow-Methods" = true
    "method.response.header.Access-Control-Allow-Origin"  = true
  }
}

resource "aws_api_gateway_integration_response" "options_download_status" {
  rest_api_id = aws_api_gateway_rest_api.backup_api.id
  resource_id = aws_api_gateway_resource.download_status.id
  http_method = aws_api_gateway_method.options_download_status.http_method
  status_code = aws_api_gateway_method_response.options_download_status.status_code
  
  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = "'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token'"
    "method.response.header.Access-Control-Allow-Methods" = "'GET,OPTIONS'"
    "method.response.header.Access-Control-Allow-Origin"  = "'*'"
  }
}

# OPTIONS for /dashboard
resource "aws_api_gateway_method" "options_dashboard" {
  rest_api_id   = aws_api_gateway_rest_api.backup_api.id
  resource_id   = aws_api_gateway_resource.dashboard.id
  http_method   = "OPTIONS"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "options_dashboard" {
  rest_api_id = aws_api_gateway_rest_api.backup_api.id
  resource_id = aws_api_gateway_resource.dashboard.id
  http_method = aws_api_gateway_method.options_dashboard.http_method
  type        = "MOCK"
  
  request_templates = {
    "application/json" = "{\"statusCode\": 200}"
  }
}

resource "aws_api_gateway_method_response" "options_dashboard" {
  rest_api_id = aws_api_gateway_rest_api.backup_api.id
  resource_id = aws_api_gateway_resource.dashboard.id
  http_method = aws_api_gateway_method.options_dashboard.http_method
  status_code = "200"
  
  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = true
    "method.response.header.Access-Control-Allow-Methods" = true
    "method.response.header.Access-Control-Allow-Origin"  = true
  }
}

resource "aws_api_gateway_integration_response" "options_dashboard" {
  rest_api_id = aws_api_gateway_rest_api.backup_api.id
  resource_id = aws_api_gateway_resource.dashboard.id
  http_method = aws_api_gateway_method.options_dashboard.http_method
  status_code = aws_api_gateway_method_response.options_dashboard.status_code
  
  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = "'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token'"
    "method.response.header.Access-Control-Allow-Methods" = "'GET,OPTIONS'"
    "method.response.header.Access-Control-Allow-Origin"  = "'*'"
  }
}

# OPTIONS for /auth/login
resource "aws_api_gateway_method" "options_auth_login" {
  rest_api_id   = aws_api_gateway_rest_api.backup_api.id
  resource_id   = aws_api_gateway_resource.auth_login.id
  http_method   = "OPTIONS"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "options_auth_login" {
  rest_api_id = aws_api_gateway_rest_api.backup_api.id
  resource_id = aws_api_gateway_resource.auth_login.id
  http_method = aws_api_gateway_method.options_auth_login.http_method
  type        = "MOCK"
  
  request_templates = {
    "application/json" = "{\"statusCode\": 200}"
  }
}

resource "aws_api_gateway_method_response" "options_auth_login" {
  rest_api_id = aws_api_gateway_rest_api.backup_api.id
  resource_id = aws_api_gateway_resource.auth_login.id
  http_method = aws_api_gateway_method.options_auth_login.http_method
  status_code = "200"
  
  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = true
    "method.response.header.Access-Control-Allow-Methods" = true
    "method.response.header.Access-Control-Allow-Origin"  = true
  }
}

resource "aws_api_gateway_integration_response" "options_auth_login" {
  rest_api_id = aws_api_gateway_rest_api.backup_api.id
  resource_id = aws_api_gateway_resource.auth_login.id
  http_method = aws_api_gateway_method.options_auth_login.http_method
  status_code = aws_api_gateway_method_response.options_auth_login.status_code
  
  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = "'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token'"
    "method.response.header.Access-Control-Allow-Methods" = "'POST,OPTIONS'"
    "method.response.header.Access-Control-Allow-Origin"  = "'*'"
  }
}

# OPTIONS for /auth/validate
resource "aws_api_gateway_method" "options_auth_validate" {
  rest_api_id   = aws_api_gateway_rest_api.backup_api.id
  resource_id   = aws_api_gateway_resource.auth_validate.id
  http_method   = "OPTIONS"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "options_auth_validate" {
  rest_api_id = aws_api_gateway_rest_api.backup_api.id
  resource_id = aws_api_gateway_resource.auth_validate.id
  http_method = aws_api_gateway_method.options_auth_validate.http_method
  type        = "MOCK"
  
  request_templates = {
    "application/json" = "{\"statusCode\": 200}"
  }
}

resource "aws_api_gateway_method_response" "options_auth_validate" {
  rest_api_id = aws_api_gateway_rest_api.backup_api.id
  resource_id = aws_api_gateway_resource.auth_validate.id
  http_method = aws_api_gateway_method.options_auth_validate.http_method
  status_code = "200"
  
  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = true
    "method.response.header.Access-Control-Allow-Methods" = true
    "method.response.header.Access-Control-Allow-Origin"  = true
  }
}

resource "aws_api_gateway_integration_response" "options_auth_validate" {
  rest_api_id = aws_api_gateway_rest_api.backup_api.id
  resource_id = aws_api_gateway_resource.auth_validate.id
  http_method = aws_api_gateway_method.options_auth_validate.http_method
  status_code = aws_api_gateway_method_response.options_auth_validate.status_code
  
  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = "'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token'"
    "method.response.header.Access-Control-Allow-Methods" = "'POST,OPTIONS'"
    "method.response.header.Access-Control-Allow-Origin"  = "'*'"
  }
}

# OPTIONS for /auth/logout
resource "aws_api_gateway_method" "options_auth_logout" {
  rest_api_id   = aws_api_gateway_rest_api.backup_api.id
  resource_id   = aws_api_gateway_resource.auth_logout.id
  http_method   = "OPTIONS"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "options_auth_logout" {
  rest_api_id = aws_api_gateway_rest_api.backup_api.id
  resource_id = aws_api_gateway_resource.auth_logout.id
  http_method = aws_api_gateway_method.options_auth_logout.http_method
  type        = "MOCK"
  
  request_templates = {
    "application/json" = "{\"statusCode\": 200}"
  }
}

resource "aws_api_gateway_method_response" "options_auth_logout" {
  rest_api_id = aws_api_gateway_rest_api.backup_api.id
  resource_id = aws_api_gateway_resource.auth_logout.id
  http_method = aws_api_gateway_method.options_auth_logout.http_method
  status_code = "200"
  
  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = true
    "method.response.header.Access-Control-Allow-Methods" = true
    "method.response.header.Access-Control-Allow-Origin"  = true
  }
}

resource "aws_api_gateway_integration_response" "options_auth_logout" {
  rest_api_id = aws_api_gateway_rest_api.backup_api.id
  resource_id = aws_api_gateway_resource.auth_logout.id
  http_method = aws_api_gateway_method.options_auth_logout.http_method
  status_code = aws_api_gateway_method_response.options_auth_logout.status_code
  
  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = "'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token'"
    "method.response.header.Access-Control-Allow-Methods" = "'POST,OPTIONS'"
    "method.response.header.Access-Control-Allow-Origin"  = "'*'"
  }
}

# Note: All outputs are now centralized in outputs.tf
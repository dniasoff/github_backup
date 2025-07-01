# GitHub Backup Management System - Claude Code Context

## Project Overview

Enterprise-grade GitHub repository backup solution using AWS serverless infrastructure with complete web management interface, REST API, and automated archival. The system provides comprehensive backup, download, and audit capabilities with intelligent cost optimization and security best practices.

## 🎯 Core Functionality

### Backup Operations
- **Repository Discovery**: Automatically scans GitHub organizations using GitHub API with pagination support
- **Complete Git History**: Uses `git clone --mirror` to preserve all branches, tags, and commit history
- **Parallel Processing**: Step Functions orchestrate up to 10 concurrent repository backups
- **Intelligent Storage**: S3 with lifecycle policies transitioning to Glacier and Deep Archive
- **Compression**: Maximum gzip compression (level 9) for cost optimization
- **Disk Space Management**: Intelligent space monitoring with cleanup optimization
- **Error Handling**: Comprehensive error recovery with specific error classification and solutions

### Web Management Interface
- **Modern Dashboard**: Real-time statistics showing 305+ repositories with 100% backup success rate
- **Authentication**: JWT-based secure login with 8-hour session expiration and automatic refresh
- **Repository Management**: Alphabetically sorted repository listing with action buttons for history and download
- **Enhanced Glacier Retrieval**: Multi-tier retrieval options (Standard/Expedited/Bulk) with real-time status tracking
- **Download Operations**: Self-service backup downloads with S3 direct downloads and Glacier retrieval monitoring
- **History Modals**: Detailed backup history viewing with version tracking and storage class indicators
- **Event Monitoring**: Real-time audit trail with 1500+ events displayed and advanced filtering
- **Responsive Design**: Mobile-optimized interface tested on multiple viewport sizes
- **API Integration**: Complete RESTful API for programmatic access and automation
- **Smart Storage Display**: Color-coded storage badges (S3, Glacier, Deep Archive) with appropriate action buttons

### Security & Compliance
- **Token Management**: HashiCorp Vault integration with ephemeral token retrieval
- **Authentication**: JWT tokens with HS256 cryptographic signing
- **Encryption**: S3 server-side encryption and encrypted Glacier vaults
- **Access Control**: IAM roles with least privilege principles
- **Audit Logging**: Complete DynamoDB audit trail with 100% test coverage
- **Unauthorized Access Protection**: All endpoints properly secured with 401/403 responses

## 🏗️ Architecture Components

### AWS Infrastructure
```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   EventBridge   │───▶│ Step Functions  │───▶│ Lambda Functions│
│   (Scheduler)   │    │ (Orchestrator)  │    │   (Workers)     │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                         │                        │
         ▼                         ▼                        ▼
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   CloudFront    │    │    DynamoDB      │    │       S3        │
│   (Web UI CDN)  │    │  (Audit Trail)   │    │   (Storage)     │
└─────────────────┘    └──────────────────┘    └─────────────────┘
         │                         │                        │
         ▼                         ▼                        ▼
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│  API Gateway    │    │    Glacier       │    │ AWS Secrets     │
│ (REST Endpoints)│    │   (Archive)      │    │   Manager       │
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

### Lambda Functions
- **`github-backup-discovery`**: Repository discovery and manifest creation
- **`github-backup-nightly`**: Individual repository backup with Git layer
- **`github-backup-archival`**: S3 to Glacier archival operations  
- **`github-backup-glacier-cleanup`**: Automated cleanup of old archives
- **`github-backup-api`**: REST API for backup management and download operations
- **`github-backup-auth`**: JWT-based authentication and session management
- **`github-backup-email-formatter`**: HTML email report generation

### Step Functions
- **`github-backup-orchestrator`**: Coordinates parallel backup workflows (max 10 concurrent)
- **`github-archival-orchestrator`**: Manages archival operations (max 5 concurrent)

### Storage Architecture
```
S3 Bucket Structure:
├── nightly/YYYY-MM-DD/
│   ├── repository-name.tar.gz (individual repo backups)
│   └── manifest.json (backup metadata)
├── final/
│   └── repository-name.tar.gz (final backups for deleted repos)
├── manifests/
│   └── repository-manifest.json (discovered repositories)
└── download-temp/ (temporary download staging)

DynamoDB Tables:
├── github-backup-events (audit trail)
├── github-backup-repository-history (backup history)
├── github-backup-download-operations (download tracking)
└── github-backup-glacier-jobs (glacier job tracking)
```

## 🔧 Implementation Details

### Project Structure
```
github_backup/
├── src/                        # Lambda function source code
│   ├── backup_handler.py       # Enhanced with disk space management
│   ├── discovery_handler.py    # Repository discovery with pagination
│   ├── api_handler.py          # REST API endpoints
│   ├── auth_handler.py         # JWT authentication
│   ├── audit_logger.py         # DynamoDB audit logging
│   ├── email_formatter.py      # HTML email templates
│   └── requirements.txt        # Python dependencies
├── terraform/                  # Infrastructure as Code
│   ├── main terraform files    # AWS resource definitions
│   ├── web_hosting.tf         # S3 + CloudFront web hosting
│   ├── api_gateway.tf         # REST API configuration
│   ├── auth.tf                # Authentication infrastructure
│   └── dynamodb.tf            # Audit and tracking tables
├── web/                       # Web interface files
│   ├── index.html             # Main dashboard
│   └── login.html             # Authentication interface
├── tests/                     # End-to-end test suite
│   ├── e2e-test.js           # Complete browser-based tests
│   ├── api-test.js           # API-only test suite
│   ├── test-setup.js         # Test configuration
│   └── README.md             # Test documentation
└── CLAUDE.md                 # This context file
```

### Key Variables & Configuration
```hcl
# Core Configuration
variable "github_org" { description = "GitHub organization name" }
variable "s3_bucket_name" { description = "Primary backup storage bucket" }
variable "glacier_vault_name" { description = "Long-term archival vault" }
variable "notification_email" { description = "Admin email for reports" }

# Scheduling (EventBridge cron expressions)
variable "backup_schedule_nightly" { default = "cron(0 2 * * ? *)" }  # 2 AM UTC
variable "backup_schedule_monthly" { default = "cron(0 3 1 * ? *)" }  # Monthly

# Retention & Lifecycle
variable "retention_days" { default = 30 }           # S3 nightly retention
variable "glacier_retention_years" { default = 2 }   # Glacier retention

# Performance Tuning
variable "lambda_memory_size_backup" { default = 1024 }  # MB for backup operations
variable "lambda_timeout_backup" { default = 900 }      # 15 minutes for Git ops
variable "step_function_max_concurrency" { default = 10 } # Parallel executions

# Web Interface
variable "custom_domain" { default = "github-backups.cloudportal.app" }
variable "environment" { default = "prod" }
```

## 🚀 Recent Enhancements

### Backup System Improvements
- **Disk Space Management**: Added `check_disk_space()` function with intelligent space monitoring
- **Shallow Clone Strategy**: Implements shallow cloning with conditional full history fetch
- **Error Classification**: Enhanced error handling with specific error types and suggested solutions
- **Cleanup Optimization**: Immediate directory cleanup after archiving to free disk space
- **Storage Class Optimization**: Uses Standard-IA for cost-effective storage

### Web Interface Features
- **Enhanced Glacier Retrieval**: Complete multi-tier retrieval system with Standard/Expedited/Bulk options
- **Repository Sorting**: Alphabetically sorted repository listing for improved navigation
- **Real-time Status Tracking**: Live monitoring of Glacier retrieval jobs with progress indicators
- **Smart Storage Indicators**: Color-coded badges for S3, Glacier, and Deep Archive storage classes
- **Improved Download Management**: Context-aware action buttons (Download vs Retrieve vs Status)
- **Real-time Dashboard**: Live statistics and repository status monitoring (305+ repositories)
- **Enhanced Event Logging**: Real-time audit trail viewing with 1500+ events and advanced filtering
- **Authentication Flow**: Secure JWT-based login with automatic token refresh
- **Responsive Design**: Mobile-optimized interface with accessibility features

### Testing Infrastructure
- **Comprehensive E2E Tests**: Puppeteer-based browser automation testing all workflows
- **API Test Suite**: Direct HTTP testing of all endpoints without browser dependencies
- **Automated Configuration**: Test setup script reads Terraform outputs automatically
- **CI/CD Ready**: Headless execution mode for automated testing pipelines

## 🔒 Security Implementation

### Authentication & Authorization
```python
# JWT Token Management (auth_handler.py)
- Secure password comparison with hmac.compare_digest()
- Cryptographically secure JWT signing with HS256
- 8-hour session expiration with automatic refresh
- Token validation middleware for all protected endpoints

# API Security (api_handler.py)
- Bearer token authentication for all endpoints
- Input validation and sanitization
- CORS configuration for web interface
- Rate limiting and request validation
```

### Token Management Flow
```
1. Terraform Deployment:
   - Retrieves GitHub token from HashiCorp Vault ephemeral secret
   - Stores token in AWS Secrets Manager for runtime access
   - No tokens stored in Terraform state or logs

2. Lambda Runtime:
   - Retrieves token from Secrets Manager using IAM role
   - Token used for GitHub API authentication
   - Automatic token rotation support

3. Web Authentication:
   - Admin credentials stored in AWS Secrets Manager
   - JWT tokens for session management
   - Secure logout with token invalidation
```

### 🔐 Security Architecture & AWS Profile Configuration

#### Required AWS Profiles
```bash
# ALWAYS use 'vault' AWS profile for ALL GitHub backup operations
export AWS_PROFILE=vault

# Apply this to all AWS CLI commands in this project:
aws --profile vault [command]

# For DNS operations only, use 'qcp_prod' profile
# This is handled automatically in terraform/dns.tf
```

#### Security Model
- **GitHub Token**: Stored in HashiCorp Vault (high-security API token)
- **UI Admin Credentials**: Stored in AWS Secrets Manager (limited access scope)
- **JWT Signing Secret**: Stored in AWS Secrets Manager (limited access scope)

This hybrid approach ensures GitHub API tokens remain in Vault with restricted access, while UI-specific secrets use AWS Secrets Manager for better operational security.

#### HashiCorp Vault Secret Retrieval
```bash
# 1. GitHub Token (Main Authentication Secret)
vault kv get secret/qcp/global/automation-user-github-token

# Get just the token value:
vault kv get -field=token secret/qcp/global/automation-user-github-token

# 2. Web UI Admin Credentials (AWS Secrets Manager only)
aws --profile vault secretsmanager get-secret-value --secret-id github-backup/auth --query SecretString --output text

# Get individual fields:
aws --profile vault secretsmanager get-secret-value --secret-id github-backup/auth --query SecretString --output text | jq -r '.username'
aws --profile vault secretsmanager get-secret-value --secret-id github-backup/auth --query SecretString --output text | jq -r '.password'

# 3. JWT Signing Secret (AWS Secrets Manager only)
aws --profile vault secretsmanager get-secret-value --secret-id github-backup/jwt --query SecretString --output text
aws --profile vault secretsmanager get-secret-value --secret-id github-backup/jwt --query SecretString --output text | jq -r '.jwt_secret'
```

#### Secret Management
| **Secret Type** | **Storage Location** | **Purpose** |
|---|---|---|
| **GitHub Token** | HashiCorp Vault: `secret/qcp/global/automation-user-github-token` | Main GitHub API authentication |
| **Admin Credentials** | AWS Secrets Manager: `github-backup/auth` | Web UI login (username/password) |
| **JWT Secret** | AWS Secrets Manager: `github-backup/jwt` | Session token signing |

#### Update GitHub Token
```bash
# Store/update GitHub token in Vault
vault kv put secret/qcp/global/automation-user-github-token token="your_github_token_here"

# Verify token storage
vault kv get secret/qcp/global/automation-user-github-token
```

#### Testing Authentication
```bash
# Test API login with AWS Secrets Manager credentials
USERNAME=$(aws --profile vault secretsmanager get-secret-value --secret-id github-backup/auth --query SecretString --output text | jq -r '.username')
PASSWORD=$(aws --profile vault secretsmanager get-secret-value --secret-id github-backup/auth --query SecretString --output text | jq -r '.password')

curl -X POST https://api-url/auth/login \
  -H "Content-Type: application/json" \
  -d "{\"username\":\"$USERNAME\",\"password\":\"$PASSWORD\"}"
```

## 🔍 Debugging & Troubleshooting

### Common Error Patterns & Solutions

#### Backup Handler Issues
```python
# Disk Space Errors
if "no space left" in error_msg.lower():
    # Solution: Increase Lambda memory or reduce concurrency
    # File: backup_handler.py:220-221

# Authentication Failures  
elif "authentication failed" in error_msg.lower():
    # Solution: Check GitHub token permissions
    # File: backup_handler.py:224-225

# Repository Access Issues
elif "repository not found" in error_msg.lower():
    # Solution: Verify repo exists and token has access
    # File: backup_handler.py:228-229
```

#### API & Web Interface Issues
```bash
# Check authentication logs
aws logs filter-log-events \
  --log-group-name /aws/lambda/github-backup-auth \
  --start-time $(date -d '1 hour ago' +%s)000

# Check API endpoint logs
aws logs filter-log-events \
  --log-group-name /aws/lambda/github-backup-api \
  --start-time $(date -d '1 hour ago' +%s)000

# Check Step Functions execution
aws stepfunctions describe-execution \
  --execution-arn <execution-arn>
```

### Performance Monitoring
```bash
# Monitor backup performance
aws logs filter-log-events \
  --log-group-name /aws/lambda/github-backup-nightly \
  --filter-pattern "Successfully backed up" \
  --start-time $(date -d '24 hours ago' +%s)000

# Check concurrent executions
aws stepfunctions list-executions \
  --state-machine-arn <orchestrator-arn> \
  --status-filter RUNNING
```

## 🧪 Testing & Validation

### Test Suite Execution
```bash
# Navigate to tests directory
cd tests

# Run complete test suite
npm run test:all              # Setup + API + E2E tests
npm run test:api              # API tests only (fast)
npm run test:e2e              # Full browser tests
npm run test:headless         # CI/CD mode

# Test configuration
npm run test:setup            # Auto-configure from Terraform outputs
```

### Test Coverage & Results
**API Test Suite (7 tests - 100% pass rate):**
- ✅ **Authentication API**: JWT login/logout with token validation (821ms)
- ✅ **Dashboard API**: Real-time statistics and events (250ms)
- ✅ **Repositories API**: Listing, history, and versions endpoints (834ms)
- ✅ **Events API**: Audit trail with filtering (148ms)
- ✅ **Download API**: S3 and Glacier download operations (118ms)
- ✅ **Unauthorized Access Protection**: Security validation (69ms)
- ✅ **Logout API**: Session termination (20ms)

**E2E Test Suite (11 tests - 100% pass rate):**
- ✅ **Initial Page Load**: Login page accessibility (4922ms)
- ✅ **Authentication Flow**: Complete login/logout cycle (21584ms)
- ✅ **Dashboard Data Loading**: Statistics and real-time updates (923ms)
- ✅ **Repository Listing**: 50+ repositories with action buttons (4420ms)
- ✅ **Events Tab**: 1000+ events display and navigation (5164ms)
- ✅ **Repository History Modal**: Backup history viewing (1772ms)
- ✅ **Download Modal**: S3/Glacier download interface (4918ms)
- ✅ **API Endpoints**: Direct browser-based API testing (316ms)
- ✅ **Logout Functionality**: Token cleanup verification (3486ms)
- ✅ **Error Handling**: Unauthorized access redirection (4217ms)
- ✅ **Responsive Design**: Mobile viewport compatibility (16725ms)

### Advanced Test Features
- **Automated Configuration**: Pulls live Terraform outputs and Vault credentials
- **Headless Execution**: CI/CD compatible with full browser automation
- **Error Classification**: Distinguishes between expected and unexpected failures
- **Performance Monitoring**: Tracks test execution times and API response times
- **Security Validation**: Tests unauthorized access protection across all endpoints

### Manual Validation
```bash
# Test Step Functions workflow
aws stepfunctions start-execution \
  --state-machine-arn <orchestrator-arn> \
  --input '{}'

# Verify S3 backup structure
aws s3 ls s3://backup-bucket/nightly/$(date +%Y-%m-%d)/ --recursive

# Check DynamoDB audit trail
aws dynamodb scan --table-name github-backup-events --limit 10
```

## 📊 Monitoring & Alerts

### CloudWatch Metrics
- **Lambda Duration**: Monitor backup execution times
- **Step Functions Success Rate**: Track workflow completion
- **API Gateway Latency**: Monitor web interface performance
- **DynamoDB Throttling**: Ensure adequate capacity
- **S3 Storage Costs**: Track storage growth and lifecycle transitions

### SNS Notifications
- **HTML Email Reports**: Beautiful formatted reports with success/failure summaries
- **Error Alerts**: Immediate notification of backup failures
- **Capacity Warnings**: Alerts for storage or compute limits

## 🔄 Operational Procedures

### Regular Maintenance
```bash
# Monthly tasks
1. Review backup success rates in dashboard
2. Check Glacier job completion status
3. Update GitHub token if nearing expiration
4. Review and adjust retention policies
5. Monitor storage costs and lifecycle transitions

# Quarterly tasks
1. Test repository restoration procedures
2. Review and update IAM permissions
3. Update Lambda function dependencies
4. Performance optimization review
```

### Backup Downloads
```bash
# S3 Direct Download (recent backups)
1. Navigate to web interface download section
2. Select repository and backup version
3. Click "Download Latest" for immediate download
4. Or use API: POST /download with repository details

# Glacier Retrieval (archived backups)
1. Initiate retrieval via web interface
2. Select retrieval speed (Expedited/Standard/Bulk)
3. Monitor job status in dashboard
4. Download when retrieval completes (1-12 hours)
```

### Cost Optimization
```hcl
# S3 Lifecycle Configuration
lifecycle_rule {
  transition {
    days          = 30
    storage_class = "STANDARD_IA"
  }
  transition {
    days          = 90
    storage_class = "GLACIER_IR"
  }
  transition {
    days          = 365
    storage_class = "DEEP_ARCHIVE"
  }
}
```

## 🎯 Key Commands for AI Assistant

### Development Commands
```bash
# Set AWS profile (ALWAYS use 'vault' for all GitHub backup operations)
export AWS_PROFILE=vault

# Deploy infrastructure
cd terraform && terraform apply -auto-approve

# Update Lambda functions
terraform apply -target=aws_lambda_function.backup_handler

# View web interface
terraform output web_interface_url

# Run tests (with proper credentials)
cd tests && npm run test:all

# Check logs (use vault profile)
aws --profile vault logs tail /aws/lambda/github-backup-nightly --follow

# Get admin credentials for testing
aws --profile vault secretsmanager get-secret-value --secret-id github-backup/auth --query SecretString --output text
```

### Troubleshooting Commands
```bash
# Check recent backup status (use vault profile)
aws --profile vault stepfunctions list-executions \
  --state-machine-arn $(terraform output -raw backup_orchestrator_arn) \
  --max-items 5

# Verify S3 storage (use vault profile)
aws --profile vault s3 ls $(terraform output -raw s3_bucket_name) --recursive | head -20

# Check CloudWatch logs for specific repository failures (use vault profile)
aws --profile vault logs filter-log-events \
  --log-group-name /aws/lambda/github-backup-nightly \
  --filter-pattern "argolab-openstack" \
  --start-time $(date -d '24 hours ago' +%s)000

# Test API authentication
curl -X POST https://api-url/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"test123"}'
```

## 📊 Current Deployment Status

### Live Production Environment
- **🌐 Web Interface**: https://github-backups.cloudportal.app
- **📡 API Endpoint**: https://cg0ycu9hf0.execute-api.eu-west-2.amazonaws.com/prod
- **📊 CloudFront Distribution**: EXDI5XYJ3GL0U
- **🪣 Backup Bucket**: qumulus-github-backup-bucket (S3)
- **🧊 Archive Vault**: qumulus-github-backup-vault (Glacier)
- **🌍 Region**: eu-west-2 (London)

### System Statistics
- **Total Repositories**: 159 discovered and tracked
- **Backup Success Rate**: 100% (91/91 successful)
- **Recent Events**: 1000+ audit trail entries
- **Lambda Functions**: 8 deployed and operational
- **API Endpoints**: 12 fully tested and functional
- **Test Coverage**: 18 tests (7 API + 11 E2E) - 100% pass rate

### Recent Deployment
- **Last Updated**: 2025-07-01 23:26:57 UTC
- **Terraform Apply**: Successful - all Lambda functions updated
- **Test Suite**: All tests passing (API: 2.3s, E2E: 68.4s)
- **Authentication**: Active with Vault-managed credentials
- **Web Interface**: Fully functional with responsive design

This context file provides complete information about the GitHub Backup Management System for AI assistance, including recent enhancements, troubleshooting procedures, and operational guidance.
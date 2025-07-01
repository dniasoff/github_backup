# GitHub Backup System - End-to-End Tests

This directory contains comprehensive end-to-end tests for the GitHub Backup Management System, including both browser-based UI tests and API tests.

## Test Suite Overview

### 🔧 Available Test Files

- **`e2e-test.js`** - Complete browser-based end-to-end test suite
- **`api-test.js`** - API-only test suite (no browser required)
- **`test-setup.js`** - Configuration setup script
- **`e2e-test-configured.js`** - Auto-configured version of the E2E tests

### 🧪 Test Coverage

The test suite validates:

1. **Authentication Flow**
   - Login with valid/invalid credentials
   - Token validation
   - Session management
   - Logout functionality

2. **Dashboard Functionality**
   - Statistics loading
   - Data display
   - Real-time updates

3. **Repository Management**
   - Repository listing
   - Repository details
   - Backup history
   - Action buttons

4. **Backup Operations**
   - Backup status monitoring
   - Event logging
   - Error handling

5. **Download Functionality**
   - Download modal
   - S3 direct downloads
   - Glacier download requests

6. **API Endpoints**
   - All authenticated endpoints
   - Error responses
   - Unauthorized access protection

7. **User Interface**
   - Responsive design
   - Navigation
   - Error handling
   - Accessibility

## 🚀 Quick Start

### Prerequisites

1. **Node.js and NPM** (for test execution)
2. **Google Chrome** (for browser tests)
3. **Deployed Infrastructure** (Terraform deployment completed)
4. **Valid Credentials** (Admin username/password configured)

### Installation

```bash
# Navigate to tests directory
cd tests

# Install dependencies
npm install

# Install Chrome (if not already installed)
sudo apt update && sudo apt install -y google-chrome-stable
```

### Running Tests

#### Option 1: Complete Browser-Based E2E Tests

```bash
# Setup test configuration
node test-setup.js

# Run full E2E test suite
node e2e-test-configured.js
```

#### Option 2: API-Only Tests (Recommended for CI/CD)

```bash
# Run API tests only
node api-test.js
```

#### Option 3: Headless Mode

```bash
# Run tests in headless mode (no GUI)
HEADLESS=true node e2e-test-configured.js
```

### Environment Variables

```bash
# Test configuration
export HEADLESS=true              # Run browser in headless mode
export SLOWMO=50                  # Slow down operations (ms)
export BACKUP_UI_PASSWORD=your_password  # UI password (if different from default)

# Example
HEADLESS=true SLOWMO=100 node e2e-test-configured.js
```

## ⚙️ Configuration

### Automatic Configuration

The `test-setup.js` script automatically configures tests using:

- **Terraform outputs** for URLs and infrastructure details
- **Environment variables** for credentials
- **AWS Secrets Manager** for sensitive data (when accessible)

### Manual Configuration

If automatic setup fails, edit the CONFIG object in test files:

```javascript
const CONFIG = {
    WEB_URL: 'https://your-domain.com',
    API_URL: 'https://your-api-gateway-url.com/prod',
    TEST_USERNAME: 'admin',
    TEST_PASSWORD: 'your-password',
    TIMEOUT: 30000,
    HEADLESS: true
};
```

## 📊 Test Results

### Successful Run Example

```
🚀 Starting GitHub Backup E2E Test Suite

✅ PASS: Initial Page Load (1234ms)
✅ PASS: Authentication Flow (2156ms)
✅ PASS: Dashboard Data Loading (1876ms)
✅ PASS: Repository Listing (2341ms)
✅ PASS: Events Tab (1456ms)
✅ PASS: Download Modal (987ms)
✅ PASS: API Endpoints (2134ms)
✅ PASS: Logout Functionality (876ms)
✅ PASS: Error Handling (1234ms)
✅ PASS: Responsive Design (1567ms)

📋 Test Results Summary

Total Tests: 10
Passed: 10 ✅
Failed: 0 ❌
Success Rate: 100.0%

Total Duration: 16861ms
```

### Understanding Test Output

- **✅ PASS** - Test completed successfully
- **❌ FAIL** - Test failed with error details
- **Duration** - Time taken for each test in milliseconds
- **Success Rate** - Overall percentage of passing tests

## 🐛 Troubleshooting

### Common Issues

#### 1. Browser Launch Fails
```bash
# Install missing dependencies
sudo apt install -y google-chrome-stable ubuntu-desktop-minimal

# Run with additional Chrome flags
HEADLESS=true node e2e-test-configured.js
```

#### 2. Authentication Failures
```bash
# Check if credentials are correct
aws secretsmanager get-secret-value --secret-id "your-auth-secret-arn"

# Or manually set password
export BACKUP_UI_PASSWORD=your_actual_password
```

#### 3. Network Timeouts
```bash
# Increase timeout values
export TIMEOUT=60000
```

#### 4. Permission Issues
```bash
# Ensure AWS credentials have access to:
# - API Gateway
# - Secrets Manager (for credential retrieval)
# - CloudWatch Logs (for debugging)
```

### Debug Mode

Enable verbose logging:

```javascript
// Add to test files
page.on('console', msg => console.log('Browser:', msg.text()));
page.on('response', res => console.log('Response:', res.url(), res.status()));
```

## 🔒 Security Considerations

- **Never commit credentials** to version control
- **Use environment variables** for sensitive data
- **Rotate test credentials** regularly
- **Limit test user permissions** to minimum required
- **Run tests in isolated environments**

## 🚦 CI/CD Integration

### GitHub Actions Example

```yaml
name: E2E Tests
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      
      - name: Setup Node.js
        uses: actions/setup-node@v2
        with:
          node-version: '18'
          
      - name: Install dependencies
        run: |
          cd tests
          npm install
          
      - name: Install Chrome
        run: |
          sudo apt update
          sudo apt install -y google-chrome-stable
          
      - name: Run API tests
        run: |
          cd tests
          node api-test.js
        env:
          BACKUP_UI_PASSWORD: ${{ secrets.BACKUP_UI_PASSWORD }}
          
      - name: Run E2E tests
        run: |
          cd tests
          HEADLESS=true node e2e-test-configured.js
        env:
          BACKUP_UI_PASSWORD: ${{ secrets.BACKUP_UI_PASSWORD }}
```

### Jenkins Pipeline Example

```groovy
pipeline {
    agent any
    
    environment {
        BACKUP_UI_PASSWORD = credentials('backup-ui-password')
    }
    
    stages {
        stage('Setup') {
            steps {
                sh 'cd tests && npm install'
            }
        }
        
        stage('API Tests') {
            steps {
                sh 'cd tests && node api-test.js'
            }
        }
        
        stage('E2E Tests') {
            steps {
                sh 'cd tests && HEADLESS=true node e2e-test-configured.js'
            }
        }
    }
    
    post {
        always {
            archiveArtifacts artifacts: 'tests/screenshots/*.png', allowEmptyArchive: true
        }
    }
}
```

## 📈 Performance Testing

### Load Testing APIs

```bash
# Install artillery for load testing
npm install -g artillery

# Create load test config
artillery quick --count 10 --num 5 https://your-api-gateway-url.com/prod/dashboard
```

### Monitoring During Tests

- **CloudWatch Logs** - Lambda function logs
- **API Gateway Metrics** - Request counts and latencies  
- **DynamoDB Metrics** - Read/write capacity usage
- **S3 Metrics** - Request patterns and costs

## 🔄 Maintenance

### Regular Tasks

1. **Update Dependencies**
   ```bash
   cd tests
   npm update
   npm audit fix
   ```

2. **Refresh Test Data**
   - Clear old test repositories
   - Reset test user permissions
   - Update test scenarios

3. **Review Test Coverage**
   - Add tests for new features
   - Update tests for UI changes
   - Remove obsolete test cases

4. **Performance Optimization**
   - Reduce test execution time
   - Parallel test execution
   - Smart test selection

## 📚 Additional Resources

- [Puppeteer Documentation](https://pptr.dev/)
- [AWS API Gateway Testing](https://docs.aws.amazon.com/apigateway/latest/developerguide/api-gateway-testing.html)
- [GitHub Actions CI/CD](https://docs.github.com/en/actions)
- [Jest Testing Framework](https://jestjs.io/) (for unit tests)

## 🤝 Contributing

When adding new tests:

1. Follow existing naming conventions
2. Include comprehensive error handling
3. Add documentation for new test scenarios
4. Update this README with any new dependencies
5. Test in both headless and GUI modes

## 📝 License

These tests are part of the GitHub Backup Management System and follow the same license terms as the main project.
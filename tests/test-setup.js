/**
 * Test Setup Script for GitHub Backup E2E Tests
 * 
 * This script retrieves the necessary configuration from Terraform outputs
 * and AWS Secrets Manager to configure the E2E tests.
 */

const { execSync } = require('child_process');
const fs = require('fs');

async function setupTestConfig() {
    console.log('🔧 Setting up test configuration...');
    
    try {
        // Get Terraform outputs
        console.log('   Getting Terraform outputs...');
        const terraformOutput = JSON.parse(execSync('cd ../terraform && terraform output -json', { encoding: 'utf8' }));
        
        const webUrl = terraformOutput.web_interface_url.value;
        const apiUrl = terraformOutput.api_gateway_url.value;
        const username = terraformOutput.backup_ui_username.value;
        
        console.log(`   Web URL: ${webUrl}`);
        console.log(`   API URL: ${apiUrl}`);
        console.log(`   Username: ${username}`);
        
        // Get password from AWS Secrets Manager
        console.log('   Getting password from AWS Secrets Manager...');
        const password = execSync('aws --profile vault secretsmanager get-secret-value --secret-id github-backup/auth --query SecretString --output text | jq -r \'.password\'', { encoding: 'utf8' }).trim();
        
        // Create test configuration
        const testConfig = {
            WEB_URL: webUrl,
            API_URL: apiUrl,
            TEST_USERNAME: username,
            TEST_PASSWORD: password,
            TIMEOUT: 30000,
            LOGIN_TIMEOUT: 10000,
            API_TIMEOUT: 15000,
            HEADLESS: process.env.HEADLESS === 'true',
            SLOWMO: parseInt(process.env.SLOWMO) || 100,
            VIEWPORT: { width: 1280, height: 720 }
        };
        
        // Update the test file with actual configuration
        let testFile = fs.readFileSync('e2e-test.js', 'utf8');
        
        // Replace the CONFIG object
        const configRegex = /const CONFIG = \{[\s\S]*?\};/;
        const newConfig = `const CONFIG = ${JSON.stringify(testConfig, null, 4)};`;
        
        testFile = testFile.replace(configRegex, newConfig);
        
        fs.writeFileSync('e2e-test-configured.js', testFile);
        
        console.log('✅ Test configuration created successfully');
        console.log('   Run tests with: node e2e-test-configured.js');
        
        return testConfig;
        
    } catch (error) {
        console.error('❌ Failed to setup test configuration:', error.message);
        throw error;
    }
}

// Run setup if called directly
if (require.main === module) {
    setupTestConfig().catch(error => {
        console.error('Setup failed:', error);
        process.exit(1);
    });
}

module.exports = { setupTestConfig };
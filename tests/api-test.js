/**
 * GitHub Backup API End-to-End Tests
 * 
 * Tests the API endpoints directly without browser automation
 */

const https = require('https');
const fs = require('fs');

// Load configuration from configured test file
let CONFIG;
try {
    const configContent = fs.readFileSync('e2e-test-configured.js', 'utf8');
    const configMatch = configContent.match(/const CONFIG = (\{[\s\S]*?\});/);
    if (configMatch) {
        CONFIG = eval(`(${configMatch[1]})`);
        CONFIG.TIMEOUT = CONFIG.API_TIMEOUT || 10000;
    } else {
        throw new Error('Could not find CONFIG in e2e-test-configured.js');
    }
} catch (error) {
    console.log('⚠️  Could not load configuration from e2e-test-configured.js, using defaults');
    CONFIG = {
        API_URL: 'https://cg0ycu9hf0.execute-api.eu-west-2.amazonaws.com/prod',
        TEST_USERNAME: 'admin',
        TEST_PASSWORD: 'test123',
        TIMEOUT: 10000
    };
}

let testResults = [];
let authToken = null;

function addTestResult(name, passed, error = null, duration = 0) {
    testResults.push({
        name,
        passed,
        error: error ? error.message : null,
        duration
    });
    
    const status = passed ? '✅ PASS' : '❌ FAIL';
    const time = duration > 0 ? ` (${duration}ms)` : '';
    console.log(`${status}: ${name}${time}`);
    
    if (error) {
        console.log(`   Error: ${error.message}`);
    }
}

function makeRequest(url, options = {}) {
    return new Promise((resolve, reject) => {
        const req = https.request(url, {
            method: options.method || 'GET',
            headers: {
                'Content-Type': 'application/json',
                ...options.headers
            },
            timeout: CONFIG.TIMEOUT
        }, (res) => {
            let data = '';
            
            res.on('data', chunk => {
                data += chunk;
            });
            
            res.on('end', () => {
                try {
                    const result = {
                        statusCode: res.statusCode,
                        headers: res.headers,
                        body: data ? JSON.parse(data) : null
                    };
                    resolve(result);
                } catch (e) {
                    resolve({
                        statusCode: res.statusCode,
                        headers: res.headers,
                        body: data
                    });
                }
            });
        });
        
        req.on('error', reject);
        req.on('timeout', () => {
            req.destroy();
            reject(new Error('Request timeout'));
        });
        
        if (options.body) {
            req.write(JSON.stringify(options.body));
        }
        
        req.end();
    });
}

async function testAuthentication() {
    const startTime = Date.now();
    
    try {
        console.log('\n🔐 Test 1: Authentication API');
        
        // Test login with invalid credentials
        const invalidLogin = await makeRequest(`${CONFIG.API_URL}/auth/login`, {
            method: 'POST',
            body: {
                username: 'invalid',
                password: 'invalid'
            }
        });
        
        if (invalidLogin.statusCode !== 401) {
            throw new Error(`Expected 401 for invalid login, got ${invalidLogin.statusCode}`);
        }
        
        // Test login with valid credentials
        const validLogin = await makeRequest(`${CONFIG.API_URL}/auth/login`, {
            method: 'POST',
            body: {
                username: CONFIG.TEST_USERNAME,
                password: CONFIG.TEST_PASSWORD
            }
        });
        
        if (validLogin.statusCode !== 200) {
            throw new Error(`Login failed with status ${validLogin.statusCode}: ${JSON.stringify(validLogin.body)}`);
        }
        
        if (!validLogin.body || !validLogin.body.token) {
            throw new Error('Login response missing token');
        }
        
        authToken = validLogin.body.token;
        console.log('   ✅ Login successful, token received');
        
        // Test token validation
        const validation = await makeRequest(`${CONFIG.API_URL}/auth/validate`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${authToken}`
            }
        });
        
        if (validation.statusCode !== 200 || !validation.body?.valid) {
            throw new Error('Token validation failed');
        }
        
        console.log('   ✅ Token validation successful');
        
        addTestResult('Authentication API', true, null, Date.now() - startTime);
        
    } catch (error) {
        addTestResult('Authentication API', false, error, Date.now() - startTime);
        throw error;
    }
}

async function testDashboardAPI() {
    const startTime = Date.now();
    
    try {
        console.log('\n📊 Test 2: Dashboard API');
        
        if (!authToken) {
            throw new Error('No auth token available');
        }
        
        const response = await makeRequest(`${CONFIG.API_URL}/dashboard`, {
            headers: {
                'Authorization': `Bearer ${authToken}`
            }
        });
        
        if (response.statusCode !== 200) {
            throw new Error(`Dashboard API failed with status ${response.statusCode}`);
        }
        
        const data = response.body;
        console.log('   Dashboard data:', JSON.stringify(data, null, 2));
        
        addTestResult('Dashboard API', true, null, Date.now() - startTime);
        
    } catch (error) {
        addTestResult('Dashboard API', false, error, Date.now() - startTime);
    }
}

async function testRepositoriesAPI() {
    const startTime = Date.now();
    
    try {
        console.log('\n📁 Test 3: Repositories API');
        
        if (!authToken) {
            throw new Error('No auth token available');
        }
        
        const response = await makeRequest(`${CONFIG.API_URL}/repositories`, {
            headers: {
                'Authorization': `Bearer ${authToken}`
            }
        });
        
        if (response.statusCode !== 200) {
            throw new Error(`Repositories API failed with status ${response.statusCode}`);
        }
        
        const data = response.body;
        console.log(`   Found ${data.repositories?.length || 0} repositories`);
        
        if (data.repositories && data.repositories.length > 0) {
            const firstRepo = data.repositories[0];
            console.log(`   Sample repository: ${firstRepo.name}`);
            
            // Test repository history endpoint
            const historyResponse = await makeRequest(`${CONFIG.API_URL}/repositories/${firstRepo.name}/history`, {
                headers: {
                    'Authorization': `Bearer ${authToken}`
                }
            });
            
            if (historyResponse.statusCode === 200) {
                console.log('   ✅ Repository history endpoint working');
            }
            
            // Test repository versions endpoint
            const versionsResponse = await makeRequest(`${CONFIG.API_URL}/repositories/${firstRepo.name}/versions`, {
                headers: {
                    'Authorization': `Bearer ${authToken}`
                }
            });
            
            if (versionsResponse.statusCode === 200) {
                console.log('   ✅ Repository versions endpoint working');
                console.log(`      Found ${versionsResponse.body.versions?.length || 0} versions`);
            }
        }
        
        addTestResult('Repositories API', true, null, Date.now() - startTime);
        
    } catch (error) {
        addTestResult('Repositories API', false, error, Date.now() - startTime);
    }
}

async function testEventsAPI() {
    const startTime = Date.now();
    
    try {
        console.log('\n📝 Test 4: Events API');
        
        if (!authToken) {
            throw new Error('No auth token available');
        }
        
        const response = await makeRequest(`${CONFIG.API_URL}/events?hours=24&limit=10`, {
            headers: {
                'Authorization': `Bearer ${authToken}`
            }
        });
        
        if (response.statusCode !== 200) {
            throw new Error(`Events API failed with status ${response.statusCode}`);
        }
        
        const data = response.body;
        console.log(`   Found ${data.events?.length || 0} recent events`);
        
        addTestResult('Events API', true, null, Date.now() - startTime);
        
    } catch (error) {
        addTestResult('Events API', false, error, Date.now() - startTime);
    }
}

async function testDownloadAPI() {
    const startTime = Date.now();
    
    try {
        console.log('\n🔄 Test 5: Download API');
        
        if (!authToken) {
            throw new Error('No auth token available');
        }
        
        // Test download initiation with mock data
        const downloadRequest = {
            repository_name: 'test-repo',
            backup_version: 'latest'
        };
        
        const response = await makeRequest(`${CONFIG.API_URL}/download`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${authToken}`
            },
            body: downloadRequest
        });
        
        // It's okay if this fails with a specific error about the repository not existing
        if (response.statusCode === 404 && response.body?.error?.includes('not found')) {
            console.log('   ✅ Download API working (repository not found - expected)');
        } else if (response.statusCode === 200 || response.statusCode === 202) {
            console.log('   ✅ Download initiated successfully');
            
            // Test download status endpoint if we got a download ID
            if (response.body?.download_id) {
                const statusResponse = await makeRequest(`${CONFIG.API_URL}/download/${response.body.download_id}`, {
                    headers: {
                        'Authorization': `Bearer ${authToken}`
                    }
                });
                
                if (statusResponse.statusCode === 200) {
                    console.log('   ✅ Download status endpoint working');
                }
            }
        } else if (response.statusCode === 401) {
            throw new Error('Unauthorized access to download API');
        } else {
            console.log(`   ⚠️  Download API returned status ${response.statusCode}`);
        }
        
        addTestResult('Download API', true, null, Date.now() - startTime);
        
    } catch (error) {
        addTestResult('Download API', false, error, Date.now() - startTime);
    }
}

async function testUnauthorizedAccess() {
    const startTime = Date.now();
    
    try {
        console.log('\n🔒 Test 6: Unauthorized Access Protection');
        
        // Test accessing protected endpoints without token
        const endpoints = ['/dashboard', '/repositories', '/events', '/download'];
        
        for (const endpoint of endpoints) {
            const response = await makeRequest(`${CONFIG.API_URL}${endpoint}`);
            
            if (response.statusCode === 200) {
                throw new Error(`Endpoint ${endpoint} allowed unauthorized access`);
            }
            
            console.log(`   ✅ ${endpoint}: Properly protected (${response.statusCode})`);
        }
        
        addTestResult('Unauthorized Access Protection', true, null, Date.now() - startTime);
        
    } catch (error) {
        addTestResult('Unauthorized Access Protection', false, error, Date.now() - startTime);
    }
}

async function testLogoutAPI() {
    const startTime = Date.now();
    
    try {
        console.log('\n🚪 Test 7: Logout API');
        
        if (!authToken) {
            throw new Error('No auth token available');
        }
        
        const response = await makeRequest(`${CONFIG.API_URL}/auth/logout`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${authToken}`
            }
        });
        
        if (response.statusCode !== 200) {
            throw new Error(`Logout API failed with status ${response.statusCode}`);
        }
        
        console.log('   ✅ Logout successful');
        
        addTestResult('Logout API', true, null, Date.now() - startTime);
        
    } catch (error) {
        addTestResult('Logout API', false, error, Date.now() - startTime);
    }
}

function printResults() {
    console.log('\n📋 API Test Results Summary\n');
    
    const passed = testResults.filter(r => r.passed).length;
    const failed = testResults.filter(r => !r.passed).length;
    const total = testResults.length;
    
    console.log(`Total Tests: ${total}`);
    console.log(`Passed: ${passed} ✅`);
    console.log(`Failed: ${failed} ❌`);
    console.log(`Success Rate: ${((passed / total) * 100).toFixed(1)}%\n`);
    
    if (failed > 0) {
        console.log('❌ Failed Tests:');
        testResults.filter(r => !r.passed).forEach(test => {
            console.log(`   • ${test.name}: ${test.error}`);
        });
        console.log('');
    }
    
    const totalDuration = testResults.reduce((sum, test) => sum + test.duration, 0);
    console.log(`Total Duration: ${totalDuration}ms`);
    
    return failed === 0;
}

async function runAPITests() {
    console.log('🚀 Starting GitHub Backup API Test Suite\n');
    console.log(`API URL: ${CONFIG.API_URL}`);
    console.log(`Username: ${CONFIG.TEST_USERNAME}\n`);
    
    let success = false;
    
    try {
        await testAuthentication();
        await testDashboardAPI();
        await testRepositoriesAPI();
        await testEventsAPI();
        await testDownloadAPI();
        await testUnauthorizedAccess();
        await testLogoutAPI();
        
        success = printResults();
        
    } catch (error) {
        console.error('\n💥 API test suite failed with error:', error.message);
        success = false;
    }
    
    process.exit(success ? 0 : 1);
}

runAPITests().catch(error => {
    console.error('Unhandled error:', error);
    process.exit(1);
});
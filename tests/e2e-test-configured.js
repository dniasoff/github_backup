/**
 * GitHub Backup Management System - End-to-End Tests
 * 
 * This test suite validates the complete functionality of the GitHub backup system:
 * - Authentication flow (login/logout)
 * - Dashboard loading and data display
 * - Repository listing and management
 * - Backup initiation and monitoring
 * - Download functionality
 * - API endpoints
 * 
 * Run with: node e2e-test.js
 */

const puppeteer = require('puppeteer');

// Configuration
const CONFIG = {
    "WEB_URL": "https://github-backups.cloudportal.app",
    "API_URL": "https://cg0ycu9hf0.execute-api.eu-west-2.amazonaws.com/prod",
    "TEST_USERNAME": "admin",
    "TEST_PASSWORD": "VV6AIEoA6j-xph&nso*uqFS9vj0No5Xx",
    "TIMEOUT": 30000,
    "LOGIN_TIMEOUT": 10000,
    "API_TIMEOUT": 15000,
    "HEADLESS": false,
    "SLOWMO": 100,
    "VIEWPORT": {
        "width": 1280,
        "height": 720
    }
};

// Test state
let browser;
let page;
let testResults = [];

/**
 * Test result tracking
 */
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

/**
 * Initialize browser and page
 */
async function setup() {
    console.log('🚀 Starting GitHub Backup E2E Test Suite\n');
    
    browser = await puppeteer.launch({
        headless: process.env.HEADLESS === 'true' ? 'new' : CONFIG.HEADLESS,
        slowMo: CONFIG.SLOWMO,
        args: [
            '--no-sandbox',
            '--disable-setuid-sandbox',
            '--disable-dev-shm-usage',
            '--disable-gpu',
            '--disable-software-rasterizer'
        ]
    });
    
    page = await browser.newPage();
    await page.setViewport(CONFIG.VIEWPORT);
    
    // Set longer timeout for navigation
    page.setDefaultTimeout(CONFIG.TIMEOUT);
    page.setDefaultNavigationTimeout(CONFIG.TIMEOUT);
    
    // Listen for console errors
    page.on('console', msg => {
        if (msg.type() === 'error') {
            console.log('Browser console error:', msg.text());
        }
    });
    
    // Listen for uncaught exceptions
    page.on('pageerror', error => {
        console.log('Page error:', error.message);
    });
}

/**
 * Test 1: Initial page load and accessibility
 */
async function testInitialPageLoad() {
    const startTime = Date.now();
    
    try {
        console.log('\n📋 Test 1: Initial Page Load');
        
        // Navigate to login page
        await page.goto(CONFIG.WEB_URL, { waitUntil: 'networkidle2' });
        
        // Check if we're on the login page
        const isLoginPage = await page.$('.login-container') !== null;
        
        if (!isLoginPage) {
            throw new Error('Login page not loaded correctly');
        }
        
        // Check for required login elements
        const usernameField = await page.$('#username');
        const passwordField = await page.$('#password');
        const loginButton = await page.$('#loginBtn');
        
        if (!usernameField || !passwordField || !loginButton) {
            throw new Error('Required login form elements not found');
        }
        
        // Check page title
        const title = await page.title();
        if (!title.includes('GitHub Backup')) {
            throw new Error(`Unexpected page title: ${title}`);
        }
        
        addTestResult('Initial Page Load', true, null, Date.now() - startTime);
        
    } catch (error) {
        addTestResult('Initial Page Load', false, error, Date.now() - startTime);
        throw error;
    }
}

/**
 * Test 2: Authentication flow
 */
async function testAuthentication() {
    const startTime = Date.now();
    
    try {
        console.log('\n🔐 Test 2: Authentication Flow');
        
        // Test invalid credentials first
        await page.type('#username', 'invalid_user');
        await page.type('#password', 'invalid_pass');
        await page.click('#loginBtn');
        
        // Wait for error message
        await page.waitForSelector('#errorMessage', { visible: true, timeout: 5000 });
        
        // Clear fields and try valid credentials
        await page.evaluate(() => {
            document.getElementById('username').value = '';
            document.getElementById('password').value = '';
        });
        
        await page.type('#username', CONFIG.TEST_USERNAME);
        await page.type('#password', CONFIG.TEST_PASSWORD);
        
        // Submit login form
        await Promise.all([
            page.waitForNavigation({ waitUntil: 'networkidle2', timeout: CONFIG.LOGIN_TIMEOUT }),
            page.click('#loginBtn')
        ]);
        
        // Check if we're now on the main dashboard
        const isDashboard = await page.$('.dashboard') !== null;
        
        if (!isDashboard) {
            throw new Error('Failed to reach dashboard after login');
        }
        
        // Check for authentication indicators
        const logoutLink = await page.$('a[onclick="logout()"]');
        if (!logoutLink) {
            throw new Error('Logout link not found - authentication may have failed');
        }
        
        addTestResult('Authentication Flow', true, null, Date.now() - startTime);
        
    } catch (error) {
        addTestResult('Authentication Flow', false, error, Date.now() - startTime);
        throw error;
    }
}

/**
 * Test 3: Dashboard loading and data display
 */
async function testDashboard() {
    const startTime = Date.now();
    
    try {
        console.log('\n📊 Test 3: Dashboard Data Loading');
        
        // Wait for dashboard stats to load
        await page.waitForFunction(() => {
            const totalRepos = document.getElementById('totalRepos').textContent;
            return totalRepos && totalRepos !== '-';
        }, { timeout: CONFIG.API_TIMEOUT });
        
        // Check all dashboard stats
        const stats = await page.evaluate(() => ({
            totalRepos: document.getElementById('totalRepos').textContent,
            successfulBackups: document.getElementById('successfulBackups').textContent,
            failedBackups: document.getElementById('failedBackups').textContent,
            successRate: document.getElementById('successRate').textContent
        }));
        
        // Validate stats are loaded
        if (stats.totalRepos === '-' || stats.successRate === '-') {
            throw new Error('Dashboard statistics not loaded properly');
        }
        
        console.log('   Dashboard Stats:', stats);
        
        addTestResult('Dashboard Data Loading', true, null, Date.now() - startTime);
        
    } catch (error) {
        addTestResult('Dashboard Data Loading', false, error, Date.now() - startTime);
        throw error;
    }
}

/**
 * Test 4: Repository listing and navigation
 */
async function testRepositoryListing() {
    const startTime = Date.now();
    
    try {
        console.log('\n📁 Test 4: Repository Listing');
        
        // Ensure we're on the repositories tab
        await page.click('button[onclick="showTab(\'repositories\')"]');
        
        // Wait for repositories to load
        await page.waitForFunction(() => {
            const content = document.getElementById('repositoriesContent');
            return content && !content.textContent.includes('Loading repositories');
        }, { timeout: CONFIG.API_TIMEOUT });
        
        // Check if repositories are displayed
        const repositoryCards = await page.$$('.repository-card');
        
        if (repositoryCards.length === 0) {
            // Check if it's an empty state or an error
            const content = await page.$eval('#repositoriesContent', el => el.textContent);
            if (content.includes('No repositories found')) {
                console.log('   No repositories found (this may be expected)');
            } else {
                throw new Error('Repository list failed to load');
            }
        } else {
            console.log(`   Found ${repositoryCards.length} repositories`);
            
            // Test repository card functionality
            const firstRepo = repositoryCards[0];
            const repoName = await firstRepo.$eval('.repo-name', el => el.textContent);
            console.log(`   Testing repository: ${repoName}`);
            
            // Check for action buttons - they might be in a separate actions container
            const actionButtons = await firstRepo.$$('.repo-actions button');
            
            if (actionButtons.length < 2) {
                // Try a more general selector
                const allButtons = await firstRepo.$$('button');
                console.log(`   Found ${allButtons.length} buttons in repository card`);
                
                if (allButtons.length === 0) {
                    throw new Error('No action buttons found in repository card');
                }
            } else {
                console.log(`   Found ${actionButtons.length} action buttons`);
            }
        }
        
        addTestResult('Repository Listing', true, null, Date.now() - startTime);
        
    } catch (error) {
        addTestResult('Repository Listing', false, error, Date.now() - startTime);
        throw error;
    }
}

/**
 * Test 5: Events tab functionality
 */
async function testEventsTab() {
    const startTime = Date.now();
    
    try {
        console.log('\n📝 Test 5: Events Tab');
        
        // Click events tab
        await page.click('button[onclick="showTab(\'events\')"]');
        
        // Wait for events to load
        await page.waitForFunction(() => {
            const content = document.getElementById('eventsContent');
            return content && !content.textContent.includes('Loading events');
        }, { timeout: CONFIG.API_TIMEOUT });
        
        // Check events content
        const eventsContent = await page.$eval('#eventsContent', el => el.textContent);
        
        if (eventsContent.includes('Failed to load events')) {
            throw new Error('Events failed to load');
        }
        
        if (!eventsContent.includes('No recent events found')) {
            // Events exist, check structure
            const eventItems = await page.$$('.event-item');
            if (eventItems.length > 0) {
                console.log(`   Found ${eventItems.length} events`);
            }
        } else {
            console.log('   No recent events (this may be expected)');
        }
        
        addTestResult('Events Tab', true, null, Date.now() - startTime);
        
    } catch (error) {
        addTestResult('Events Tab', false, error, Date.now() - startTime);
        throw error;
    }
}

/**
 * Test 6: Repository History Modal
 */
async function testHistoryModal() {
    const startTime = Date.now();
    
    try {
        console.log('\n📜 Test 6: Repository History Modal');
        
        // Ensure we're on repositories tab
        await page.click('button[onclick="showTab(\'repositories\')"]');
        
        // Wait for repositories to be visible
        await page.waitForFunction(() => {
            const tab = document.getElementById('repositories');
            return tab && tab.classList.contains('active');
        });
        
        // Try to find a view history button
        const historyBtn = await page.$('button[onclick*="viewHistory"]');
        
        if (historyBtn) {
            // Click history button
            await historyBtn.click();
            
            // Wait for modal to appear
            await page.waitForSelector('#historyModal', { visible: true, timeout: 5000 });
            
            // Check modal content
            const modalVisible = await page.$eval('#historyModal', el => 
                getComputedStyle(el).display !== 'none'
            );
            
            if (!modalVisible) {
                throw new Error('History modal not visible');
            }
            
            // Check for history table
            const historyTable = await page.$('.backup-history-table');
            if (!historyTable) {
                throw new Error('History table not found in modal');
            }
            
            // Close modal
            const closeBtn = await page.$('#historyModal .close');
            await closeBtn.click();
            
            // Verify modal is closed
            await page.waitForFunction(() => {
                const modal = document.getElementById('historyModal');
                return getComputedStyle(modal).display === 'none';
            });
            
            console.log('   History modal functionality verified');
        } else {
            console.log('   No history buttons available (no repositories to test with)');
        }
        
        addTestResult('Repository History Modal', true, null, Date.now() - startTime);
        
    } catch (error) {
        addTestResult('Repository History Modal', false, error, Date.now() - startTime);
        throw error;
    }
}

/**
 * Test 7: Download functionality UI
 */
async function testDownloadModal() {
    const startTime = Date.now();
    
    try {
        console.log('\n🔄 Test 7: Download Modal');
        
        // Try to find a download button
        const downloadBtn = await page.$('button[onclick*="initiateDownload"]');
        
        if (downloadBtn) {
            // Click download button
            await downloadBtn.click();
            
            // Wait for modal to appear
            await page.waitForSelector('#downloadModal', { visible: true, timeout: 5000 });
            
            // Check modal content
            const modalVisible = await page.$eval('#downloadModal', el => 
                getComputedStyle(el).display !== 'none'
            );
            
            if (!modalVisible) {
                throw new Error('Download modal not visible');
            }
            
            // Check modal form elements
            const modalContent = await page.$('#downloadModalContent');
            if (!modalContent) {
                throw new Error('Download modal content not found');
            }
            
            // Check for download options - look for version select or other elements
            const versionSelect = await page.$('#versionSelect');
            const downloadContent = await page.$eval('#downloadModalContent', el => el.textContent);
            
            if (!versionSelect && !downloadContent.includes('backup')) {
                console.log('   Warning: No version select found, but modal is displayed');
            } else {
                console.log('   Download modal content verified');
            }
            
            // Close modal
            const closeBtn = await page.$('#downloadModal .close');
            await closeBtn.click();
            
            // Verify modal is closed
            await page.waitForFunction(() => {
                const modal = document.getElementById('downloadModal');
                return getComputedStyle(modal).display === 'none';
            });
            
            console.log('   Download modal functionality verified');
        } else {
            console.log('   No download buttons available (no repositories to test with)');
        }
        
        addTestResult('Download Modal', true, null, Date.now() - startTime);
        
    } catch (error) {
        addTestResult('Download Modal', false, error, Date.now() - startTime);
        throw error;
    }
}

/**
 * Test 8: API endpoints direct testing
 */
async function testAPIEndpoints() {
    const startTime = Date.now();
    
    try {
        console.log('\n🌐 Test 8: API Endpoints');
        
        // Get auth token from localStorage
        const token = await page.evaluate(() => localStorage.getItem('backup_token'));
        
        if (!token) {
            throw new Error('No authentication token found');
        }
        
        // Test API endpoints using page.evaluate to make requests from browser context
        const apiTests = await page.evaluate(async (apiUrl, authToken) => {
            const headers = { 'Authorization': `Bearer ${authToken}` };
            const results = {};
            
            // Test dashboard endpoint
            try {
                const dashResponse = await fetch(`${apiUrl}/dashboard`, { headers });
                results.dashboard = {
                    status: dashResponse.status,
                    ok: dashResponse.ok
                };
            } catch (e) {
                results.dashboard = { error: e.message };
            }
            
            // Test repositories endpoint
            try {
                const reposResponse = await fetch(`${apiUrl}/repositories`, { headers });
                results.repositories = {
                    status: reposResponse.status,
                    ok: reposResponse.ok
                };
            } catch (e) {
                results.repositories = { error: e.message };
            }
            
            // Test events endpoint
            try {
                const eventsResponse = await fetch(`${apiUrl}/events?hours=24&limit=10`, { headers });
                results.events = {
                    status: eventsResponse.status,
                    ok: eventsResponse.ok
                };
            } catch (e) {
                results.events = { error: e.message };
            }
            
            return results;
        }, CONFIG.API_URL, token);
        
        // Check API test results
        const failedEndpoints = [];
        
        Object.entries(apiTests).forEach(([endpoint, result]) => {
            if (result.error || !result.ok) {
                failedEndpoints.push(`${endpoint}: ${result.error || `HTTP ${result.status}`}`);
            } else {
                console.log(`   ✅ ${endpoint}: HTTP ${result.status}`);
            }
        });
        
        if (failedEndpoints.length > 0) {
            throw new Error(`API endpoints failed: ${failedEndpoints.join(', ')}`);
        }
        
        addTestResult('API Endpoints', true, null, Date.now() - startTime);
        
    } catch (error) {
        addTestResult('API Endpoints', false, error, Date.now() - startTime);
        throw error;
    }
}

/**
 * Test 9: Logout functionality
 */
async function testLogout() {
    const startTime = Date.now();
    
    try {
        console.log('\n🚪 Test 9: Logout Functionality');
        
        // Click logout link
        await page.click('a[onclick="logout()"]');
        
        // Wait for redirect to login page
        await page.waitForFunction(() => {
            return window.location.pathname.includes('login') || 
                   document.querySelector('.login-container') !== null;
        }, { timeout: CONFIG.LOGIN_TIMEOUT });
        
        // Verify we're back on login page
        const loginContainer = await page.$('.login-container');
        if (!loginContainer) {
            throw new Error('Not redirected to login page after logout');
        }
        
        // Verify token is cleared
        const token = await page.evaluate(() => localStorage.getItem('backup_token'));
        if (token) {
            throw new Error('Authentication token not cleared after logout');
        }
        
        addTestResult('Logout Functionality', true, null, Date.now() - startTime);
        
    } catch (error) {
        addTestResult('Logout Functionality', false, error, Date.now() - startTime);
        throw error;
    }
}

/**
 * Test 10: Error handling and edge cases
 */
async function testErrorHandling() {
    const startTime = Date.now();
    
    try {
        console.log('\n⚠️  Test 10: Error Handling');
        
        // Test accessing dashboard without authentication
        await page.goto(`${CONFIG.WEB_URL}/index.html`, { waitUntil: 'networkidle2' });
        
        // Should be redirected to login
        await page.waitForFunction(() => {
            return window.location.pathname.includes('login') || 
                   document.querySelector('.login-container') !== null;
        }, { timeout: 5000 });
        
        const onLoginPage = await page.$('.login-container') !== null;
        if (!onLoginPage) {
            throw new Error('Unauthenticated access not properly redirected to login');
        }
        
        addTestResult('Error Handling', true, null, Date.now() - startTime);
        
    } catch (error) {
        addTestResult('Error Handling', false, error, Date.now() - startTime);
        throw error;
    }
}

/**
 * Test 11: Responsive design (mobile viewport)
 */
async function testResponsiveDesign() {
    const startTime = Date.now();
    
    try {
        console.log('\n📱 Test 11: Responsive Design');
        
        // Set mobile viewport
        await page.setViewport({ width: 375, height: 667 });
        
        // Login again for mobile test
        await page.type('#username', CONFIG.TEST_USERNAME);
        await page.type('#password', CONFIG.TEST_PASSWORD);
        
        await Promise.all([
            page.waitForNavigation({ waitUntil: 'networkidle2' }),
            page.click('#loginBtn')
        ]);
        
        // Check mobile layout
        const dashboard = await page.$('.dashboard');
        if (!dashboard) {
            throw new Error('Dashboard not found in mobile view');
        }
        
        // Check navigation tabs work in mobile
        await page.click('button[onclick="showTab(\'events\')"]');
        await new Promise(resolve => setTimeout(resolve, 1000));
        
        const eventsTab = await page.$('#events.active');
        if (!eventsTab) {
            throw new Error('Tab navigation not working in mobile view');
        }
        
        // Reset viewport
        await page.setViewport(CONFIG.VIEWPORT);
        
        addTestResult('Responsive Design', true, null, Date.now() - startTime);
        
    } catch (error) {
        addTestResult('Responsive Design', false, error, Date.now() - startTime);
        throw error;
    }
}

/**
 * Print final test results
 */
function printResults() {
    console.log('\n📋 Test Results Summary\n');
    
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

/**
 * Cleanup resources
 */
async function cleanup() {
    if (browser) {
        await browser.close();
    }
}

/**
 * Main test execution
 */
async function runTests() {
    let success = false;
    
    try {
        await setup();
        
        // Run all tests in sequence
        await testInitialPageLoad();
        await testAuthentication();
        await testDashboard();
        await testRepositoryListing();
        await testEventsTab();
        await testHistoryModal();
        await testDownloadModal();
        await testAPIEndpoints();
        await testLogout();
        await testErrorHandling();
        await testResponsiveDesign();
        
        success = printResults();
        
    } catch (error) {
        console.error('\n💥 Test suite failed with error:', error.message);
        success = false;
    } finally {
        await cleanup();
    }
    
    // Exit with appropriate code
    process.exit(success ? 0 : 1);
}

// Handle process signals
process.on('SIGINT', async () => {
    console.log('\n🛑 Test suite interrupted');
    await cleanup();
    process.exit(1);
});

process.on('SIGTERM', async () => {
    console.log('\n🛑 Test suite terminated');
    await cleanup();
    process.exit(1);
});

// Run the tests
runTests().catch(async (error) => {
    console.error('Unhandled error:', error);
    await cleanup();
    process.exit(1);
});
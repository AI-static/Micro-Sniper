// API Configuration
const API_BASE = window.location.origin;
let API_KEY = localStorage.getItem('microsniper_api_key') || '';

// Axios configuration
const api = axios.create({
    baseURL: API_BASE,
    headers: {
        'Content-Type': 'application/json'
    }
});

// Set auth interceptor
api.interceptors.request.use(config => {
    if (API_KEY) {
        config.headers['Authorization'] = `Bearer ${API_KEY}`;
    }
    return config;
});

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    if (API_KEY) {
        showMainApp();
    }
});

// Login function
async function login() {
    const apiKey = document.getElementById('apiKeyInput').value.trim();
    const errorDiv = document.getElementById('loginError');
    const loading = document.querySelector('#loginScreen .loading');

    if (!apiKey) {
        errorDiv.textContent = 'Please enter your API key';
        errorDiv.classList.remove('hidden');
        return;
    }

    loading.classList.add('active');

    try {
        // Temporarily set the API key for validation
        const tempApi = axios.create({
            baseURL: API_BASE,
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${apiKey}`
            }
        });

        // Validate API key by calling api-keys endpoint
        const response = await tempApi.get('/identity/api-keys');

        if (response.data && response.data.code === 0) {
            API_KEY = apiKey;
            localStorage.setItem('microsniper_api_key', apiKey);
            showMainApp();
        } else {
            throw new Error('Invalid response');
        }
    } catch (error) {
        console.error('Login error:', error);
        const errorMsg = error.response?.data?.message || error.message || 'Invalid API key. Please try again.';
        errorDiv.textContent = errorMsg;
        errorDiv.classList.remove('hidden');
    } finally {
        loading.classList.remove('active');
    }
}

// Logout function
function logout() {
    API_KEY = '';
    localStorage.removeItem('microsniper_api_key');
    document.getElementById('mainApp').classList.add('hidden');
    document.getElementById('loginScreen').classList.remove('hidden');
    document.getElementById('apiKeyInput').value = '';
}

// Show main app
function showMainApp() {
    document.getElementById('loginScreen').classList.add('hidden');
    document.getElementById('mainApp').classList.remove('hidden');
    document.getElementById('apiKeyDisplay').textContent =
        API_KEY.substring(0, 8) + '...';

    // Load platforms
    loadPlatforms();

    // Load tasks
    refreshTasks();
}

// Show section
function showSection(section) {
    // Hide all sections
    document.getElementById('tasksSection').classList.add('hidden');
    document.getElementById('connectorsSection').classList.add('hidden');
    document.getElementById('platformsSection').classList.add('hidden');

    // Show selected section
    document.getElementById(section + 'Section').classList.remove('hidden');

    // Update nav
    document.querySelectorAll('.nav-link').forEach(link => {
        link.classList.remove('active');
    });
    event.target.classList.add('active');

    // Refresh data if needed
    if (section === 'platforms') {
        loadPlatforms();
    } else if (section === 'tasks') {
        refreshTasks();
    }
}

// Toggle loading state
function setLoading(btnId, loading) {
    const btn = document.querySelector(`#${btnId} .loading`);
    if (btn) {
        if (loading) {
            btn.classList.add('active');
            document.getElementById(btnId).disabled = true;
        } else {
            btn.classList.remove('active');
            document.getElementById(btnId).disabled = false;
        }
    }
}

// Show toast notification
function showToast(title, message, type = 'info') {
    const toastEl = document.getElementById('liveToast');
    const toastTitle = document.getElementById('toastTitle');
    const toastBody = document.getElementById('toastBody');

    toastTitle.textContent = title;
    toastBody.textContent = message;

    const toast = new bootstrap.Toast(toastEl);
    toast.show();
}

// ============ TASK FUNCTIONS ============

// Create creator monitor task
async function createCreatorTask(event) {
    event.preventDefault();
    setLoading('creatorTaskResult', true);

    const platform = document.getElementById('creatorPlatform').value;
    const creatorIds = document.getElementById('creatorIds').value
        .split('\n')
        .map(id => id.trim())
        .filter(id => id);

    const days = document.getElementById('monitorDays').value;

    if (!platform) {
        displayError('creatorTaskResult', { response: { data: { message: '请选择平台' } } });
        showToast('Error', '请选择平台', 'error');
        setLoading('creatorTaskResult', false);
        return;
    }

    try {
        const response = await api.post(`/sniper/${platform}/harvest`, {
            creator_ids: creatorIds,
            days: parseInt(days)
        });

        displayResult('creatorTaskResult', response.data);
        showToast('Success', 'Creator monitor task created successfully!');

        // Refresh task list
        setTimeout(() => refreshTasks(), 1000);
    } catch (error) {
        displayError('creatorTaskResult', error);
        showToast('Error', 'Failed to create task', 'error');
    } finally {
        setLoading('creatorTaskResult', false);
    }
}

// Create trend analysis task
async function createTrendTask(event) {
    event.preventDefault();
    setLoading('trendTaskResult', true);

    const platform = document.getElementById('trendPlatform').value;
    const keywords = document.getElementById('trendKeywords').value
        .split('\n')
        .map(kw => kw.trim())
        .filter(kw => kw);

    if (!platform) {
        displayError('trendTaskResult', { response: { data: { message: '请选择平台' } } });
        showToast('Error', '请选择平台', 'error');
        setLoading('trendTaskResult', false);
        return;
    }

    try {
        const response = await api.post(`/sniper/${platform}/trend`, {
            keywords: keywords
        });

        displayResult('trendTaskResult', response.data);
        showToast('Success', 'Trend analysis task created successfully!');

        // Refresh task list
        setTimeout(() => refreshTasks(), 1000);
    } catch (error) {
        displayError('trendTaskResult', error);
        showToast('Error', 'Failed to create task', 'error');
    } finally {
        setLoading('trendTaskResult', false);
    }
}

// Refresh task list
async function refreshTasks() {
    const container = document.getElementById('taskListContainer');
    container.innerHTML = `
        <div class="text-center py-5">
            <div class="spinner-border text-primary" role="status"></div>
            <p class="mt-3 text-muted">Loading tasks...</p>
        </div>
    `;

    try {
        const response = await api.post('/sniper/tasks', {
            limit: 20
        });

        const tasks = response.data.data.tasks;

        if (tasks.length === 0) {
            container.innerHTML = `
                <div class="text-center text-muted py-5">
                    <i class="bi bi-inbox" style="font-size: 48px; display: block; margin-bottom: 16px;"></i>
                    <p>No tasks yet. Create your first task!</p>
                </div>
            `;
        } else {
            container.innerHTML = tasks.map((task, index) => `
                <div class="task-card">
                    <div class="d-flex justify-content-between align-items-start mb-2">
                        <div>
                            <h5 class="mb-1">
                                <i class="bi bi-${getTaskIcon(task.task_type)}"></i>
                                ${formatTaskType(task.task_type)}
                            </h5>
                            <small class="text-muted">Task ID: ${task.id}</small>
                        </div>
                        <span class="task-status task-${task.status.toLowerCase()}">${task.status}</span>
                    </div>
                    <div class="mb-2">
                        <small class="text-muted">
                            <i class="bi bi-clock"></i> ${task.created_at || 'Just now'}
                        </small>
                    </div>
                    ${task.progress !== undefined ? `
                        <div class="mb-2">
                            <div class="d-flex justify-content-between mb-1">
                                <small>Progress</small>
                                <small>${task.progress}%</small>
                            </div>
                            <div class="progress" style="height: 6px;">
                                <div class="progress-bar" style="width: ${task.progress}%"></div>
                            </div>
                        </div>
                    ` : ''}
                    ${task.error ? `
                        <div class="alert alert-danger alert-sm mb-0">
                            <small><i class="bi bi-exclamation-triangle"></i> ${task.error}</small>
                        </div>
                    ` : ''}
                    ${task.logs && task.logs.length > 0 ? `
                        <div class="mt-2">
                            <button class="btn btn-sm btn-outline-secondary" type="button" data-bs-toggle="collapse" data-bs-target="#logsCollapse${index}" aria-expanded="false" aria-controls="logsCollapse${index}">
                                <i class="bi bi-journal-text"></i> View Logs (${task.logs.length})
                            </button>
                            <div class="collapse mt-2" id="logsCollapse${index}">
                                <div class="card card-body bg-light">
                                    <pre class="mb-0" style="font-size: 0.85rem; max-height: 300px; overflow-y: auto;">${JSON.stringify(task.logs, null, 2)}</pre>
                                </div>
                            </div>
                        </div>
                    ` : ''}
                </div>
            `).join('');
        }
    } catch (error) {
        console.error('Failed to load tasks:', error);
        container.innerHTML = `
            <div class="alert alert-danger">
                <i class="bi bi-exclamation-triangle"></i> Failed to load tasks: ${error.response?.data?.message || error.message}
            </div>
        `;
    }
}

function getTaskIcon(taskType) {
    const icons = {
        'creator_monitor': 'person-badge',
        'trend_analysis': 'graph-up',
        'default': 'task'
    };
    return icons[taskType] || icons['default'];
}

function formatTaskType(taskType) {
    const names = {
        'creator_monitor': 'Creator Monitor',
        'trend_analysis': 'Trend Analysis'
    };
    return names[taskType] || taskType;
}

// Query task by ID
async function queryTask() {
    const taskId = document.getElementById('taskId').value.trim();
    if (!taskId) {
        showToast('Error', 'Please enter a task ID', 'error');
        return;
    }

    try {
        const response = await api.get(`/sniper/task/${taskId}`);
        displayTaskDetail(response.data);
    } catch (error) {
        showToast('Error', 'Failed to fetch task details', 'error');
    }
}

// Query task logs
async function queryTaskLogs() {
    const taskId = document.getElementById('taskId').value.trim();
    if (!taskId) {
        showToast('Error', 'Please enter a task ID', 'error');
        return;
    }

    try {
        const response = await api.get(`/sniper/task/${taskId}/logs`);
        displayTaskLogs(response.data);
    } catch (error) {
        showToast('Error', 'Failed to fetch task logs', 'error');
    }
}

// ============ CONNECTOR FUNCTIONS ============

// Extract content
async function extractContent(event) {
    event.preventDefault();
    setLoading('extractResult', true);

    const platform = document.getElementById('extractPlatform').value;
    const urls = document.getElementById('extractUrls').value
        .split('\n')
        .map(url => url.trim())
        .filter(url => url);

    try {
        const response = await api.post('/connectors/extract-summary', {
            urls: urls,
            platform: platform,
            concurrency: 3
        });

        displayExtractResults('extractResult', response.data);
        showToast('Success', 'Content extraction completed!');
    } catch (error) {
        displayError('extractResult', error);
        showToast('Error', 'Extraction failed', 'error');
    } finally {
        setLoading('extractResult', false);
    }
}

// Harvest content
async function harvestContent(event) {
    event.preventDefault();
    setLoading('harvestResult', true);

    const platform = document.getElementById('harvestPlatform').value;
    const creatorIds = document.getElementById('harvestCreatorIds').value
        .split('\n')
        .map(id => id.trim())
        .filter(id => id);
    const limit = parseInt(document.getElementById('harvestLimit').value);

    try {
        const response = await api.post('/connectors/harvest', {
            platform: platform,
            creator_ids: creatorIds,
            limit: limit
        });

        displayResult('harvestResult', response.data);
        showToast('Success', 'Harvest completed successfully!');
    } catch (error) {
        displayError('harvestResult', error);
        showToast('Error', 'Harvest failed', 'error');
    } finally {
        setLoading('harvestResult', false);
    }
}

// Search and extract
async function searchAndExtract(event) {
    event.preventDefault();
    setLoading('searchResult', true);

    const platform = document.getElementById('searchPlatform').value;
    const keywords = document.getElementById('searchKeywords').value
        .split('\n')
        .map(kw => kw.trim())
        .filter(kw => kw);
    const limit = parseInt(document.getElementById('searchLimit').value);

    try {
        const response = await api.post('/connectors/search-and-extract', {
            platform: platform,
            keywords: keywords,
            limit: limit
        });

        displayResult('searchResult', response.data);
        showToast('Success', 'Search completed successfully!');
    } catch (error) {
        displayError('searchResult', error);
        showToast('Error', 'Search failed', 'error');
    } finally {
        setLoading('searchResult', false);
    }
}

// ============ PLATFORM FUNCTIONS ============

// Load platforms
async function loadPlatforms() {
    const container = document.getElementById('platformsList');

    try {
        const response = await api.get('/connectors/platforms');
        const platforms = response.data.data.platforms;

        container.innerHTML = platforms.map(platform => `
            <div class="col-md-4 mb-4">
                <div class="platform-card">
                    <div class="platform-icon">${getPlatformIcon(platform.name)}</div>
                    <div class="platform-name">${platform.display_name}</div>
                    <div class="platform-desc">${platform.description}</div>
                    <div class="mt-3">
                        ${platform.features.map(feature =>
                            `<span class="feature-badge feature-enabled">${feature}</span>`
                        ).join('')}
                    </div>
                </div>
            </div>
        `).join('');
    } catch (error) {
        container.innerHTML = `
            <div class="col-12">
                <div class="alert alert-danger">
                    <i class="bi bi-exclamation-triangle"></i> Failed to load platforms
                </div>
            </div>
        `;
    }
}

function getPlatformIcon(name) {
    const icons = {
        'xiaohongshu': '📕',
        'wechat': '💬',
        'generic': '🌐'
    };
    return icons[name] || '📦';
}

// ============ DISPLAY FUNCTIONS ============

// Display result
function displayResult(containerId, data) {
    const container = document.getElementById(containerId);
    container.innerHTML = `
        <div class="alert alert-success">
            <i class="bi bi-check-circle"></i> ${data.message || 'Operation successful'}
        </div>
        ${data.data ? formatResultData(data.data) : ''}
    `;
}

// Display error
function displayError(containerId, error) {
    const container = document.getElementById(containerId);
    const message = error.response?.data?.message || error.message || 'An error occurred';
    container.innerHTML = `
        <div class="alert alert-danger">
            <i class="bi bi-exclamation-triangle"></i> ${message}
        </div>
    `;
}

// Format result data as cards
function formatResultData(data) {
    if (!data) return '';

    if (data.results) {
        // Extract results
        const results = Object.entries(data.results).map(([key, value]) => {
            if (value.success) {
                return `
                    <div class="result-item">
                        <div class="result-title">
                            <i class="bi bi-check-circle-fill text-success"></i> ${key}
                        </div>
                        <div class="result-meta">
                            ${value.note_count || value.result_count || 0} items extracted
                        </div>
                    </div>
                `;
            } else {
                return `
                    <div class="result-item">
                        <div class="result-title">
                            <i class="bi bi-x-circle-fill text-danger"></i> ${key}
                        </div>
                        <div class="result-meta text-danger">
                            ${value.error || 'Failed'}
                        </div>
                    </div>
                `;
            }
        }).join('');

        return `<div class="mt-3">${results}</div>`;
    }

    // Generic data display
    return `<pre class="mt-3">${JSON.stringify(data, null, 2)}</pre>`;
}

// Display extract results
function displayExtractResults(containerId, data) {
    const container = document.getElementById(containerId);
    container.innerHTML = `
        <div class="alert alert-success">
            <i class="bi bi-check-circle"></i> Extraction completed
        </div>
    `;
}

// Display task detail
function displayTaskDetail(data) {
    const container = document.getElementById('taskDetailContent');
    container.innerHTML = `
        <div class="mb-3">
            <strong>Task ID:</strong> ${data.data.task_id}
        </div>
        <div class="mb-3">
            <strong>Status:</strong>
            <span class="task-status task-${data.data.status}">${data.data.status}</span>
        </div>
        <div class="mb-3">
            <strong>Progress:</strong> ${data.data.progress}%
            <div class="progress mt-2">
                <div class="progress-bar" style="width: ${data.data.progress}%"></div>
            </div>
        </div>
        ${data.data.result ? `<pre>${JSON.stringify(data.data.result, null, 2)}</pre>` : ''}
    `;

    const modal = new bootstrap.Modal(document.getElementById('taskDetailModal'));
    modal.show();
}

// Display task logs
function displayTaskLogs(data) {
    const container = document.getElementById('taskDetailContent');
    const logs = data.data.logs || [];

    container.innerHTML = `
        <div class="mb-3">
            <strong>Task ID:</strong> ${data.data.task_id}
        </div>
        <div>
            <strong>Logs:</strong>
            <pre>${JSON.stringify(logs, null, 2)}</pre>
        </div>
    `;

    const modal = new bootstrap.Modal(document.getElementById('taskDetailModal'));
    modal.show();
}
// ============ AUTH/LOGIN FUNCTIONS ============

// Load auth status for all platforms
async function loadAuthStatus() {
    const container = document.getElementById('authPlatformsList');
    container.innerHTML = `
        <div class="col-12">
            <div class="text-center py-5">
                <div class="spinner-border text-primary" role="status"></div>
                <p class="mt-3 text-muted">Loading login status...</p>
            </div>
        </div>
    `;

    try {
        const response = await api.get('/connectors/platforms');
        const platforms = response.data.data.platforms;

        container.innerHTML = platforms.map(platform => `
            <div class="col-md-6 mb-4">
                <div class="auth-card">
                    <div class="d-flex align-items-center mb-3">
                        <div class="auth-platform-icon">${getPlatformIcon(platform.name)}</div>
                        <div class="flex-grow-1">
                            <h5 class="mb-0">${platform.display_name}</h5>
                            <small class="text-muted">${platform.description}</small>
                        </div>
                        <div class="auth-status-badge status-checking" id="status-${platform.name}">
                            <i class="bi bi-arrow-repeat spin"></i> Checking...
                        </div>
                    </div>
                    <div class="d-flex gap-2">
                        <button class="btn btn-outline-primary btn-sm flex-grow-1"
                                onclick="showLoginModal('${platform.name}', '${platform.display_name}', 'qrcode')">
                            <i class="bi bi-qr-code-scan"></i> QR Login
                        </button>
                        <button class="btn btn-outline-secondary btn-sm flex-grow-1"
                                onclick="showLoginModal('${platform.name}', '${platform.display_name}', 'cookie')">
                            <i class="bi bi-cookie"></i> Cookie Login
                        </button>
                    </div>
                    <div id="auth-detail-${platform.name}" class="mt-3"></div>
                </div>
            </div>
        `).join('');

        // Check login status for each platform
        for (const platform of platforms) {
            checkPlatformLoginStatus(platform.name);
        }

    } catch (error) {
        console.error('Failed to load auth status:', error);
        container.innerHTML = `
            <div class="col-12">
                <div class="alert alert-danger">
                    <i class="bi bi-exclamation-triangle"></i> Failed to load platforms
                </div>
            </div>
        `;
    }
}

// Check login status for a platform
async function checkPlatformLoginStatus(platform) {
    const statusBadge = document.getElementById(`status-${platform}`);
    const detailDiv = document.getElementById(`auth-detail-${platform}`);

    try {
        // Try to get context status
        const response = await api.get(`/connectors/context/${platform}`);
        const isLoggedIn = response.data?.data?.exists || false;

        if (isLoggedIn) {
            statusBadge.className = 'auth-status-badge status-logged-in';
            statusBadge.innerHTML = '<i class="bi bi-check-circle"></i> Logged In';
            detailDiv.innerHTML = `
                <div class="alert alert-success alert-sm mb-0">
                    <i class="bi bi-shield-check"></i> Login context is active
                    <button class="btn btn-sm btn-outline-danger float-end"
                            onclick="logoutPlatform('${platform}')">
                        <i class="bi bi-box-arrow-right"></i> Logout
                    </button>
                </div>
            `;
        } else {
            statusBadge.className = 'auth-status-badge status-logged-out';
            statusBadge.innerHTML = '<i class="bi bi-x-circle"></i> Not Logged In';
            detailDiv.innerHTML = '';
        }
    } catch (error) {
        statusBadge.className = 'auth-status-badge status-logged-out';
        statusBadge.innerHTML = '<i class="bi bi-x-circle"></i> Not Logged In';
        detailDiv.innerHTML = '';
    }
}

// Show login modal
async function showLoginModal(platform, displayName, method) {
    currentLoginPlatform = platform;
    currentLoginMethod = method;

    document.getElementById('loginModalTitle').textContent = `${displayName} - ${method === 'qrcode' ? 'QR Code' : 'Cookie'} Login`;

    // Show/hide appropriate section
    if (method === 'qrcode') {
        document.getElementById('qrLoginSection').classList.remove('hidden');
        document.getElementById('cookieLoginSection').classList.add('hidden');

        // Load QR code
        await loadQRCode(platform);
    } else {
        document.getElementById('qrLoginSection').classList.add('hidden');
        document.getElementById('cookieLoginSection').classList.remove('hidden');
    }

    const modal = new bootstrap.Modal(document.getElementById('loginModal'));
    modal.show();
}

// Load QR code
async function loadQRCode(platform) {
    const container = document.getElementById('qrCodeContainer');
    container.innerHTML = `
        <div class="spinner-border text-primary" role="status">
            <span class="visually-hidden">Loading...</span>
        </div>
    `;

    try {
        const response = await api.post('/connectors/login', {
            platform: platform,
            method: 'qrcode'
        });

        if (response.data?.data?.qrcode) {
            container.innerHTML = `
                <img src="${response.data.data.qrcode}" alt="QR Code" style="width: 200px; height: 200px;">
            `;

            // Refresh status after timeout
            setTimeout(async () => {
                await checkPlatformLoginStatus(platform);
                bootstrap.Modal.getInstance(document.getElementById('loginModal')).hide();
                showToast('Success', 'Login successful!', 'success');
            }, response.data.data.timeout * 1000);
        } else {
            container.innerHTML = `
                <div class="alert alert-danger">
                    Failed to load QR code
                </div>
            `;
        }
    } catch (error) {
        console.error('Failed to load QR code:', error);
        container.innerHTML = `
            <div class="alert alert-danger">
                ${error.response?.data?.message || 'Failed to load QR code'}
            </div>
        `;
    }
}

// Submit cookie login
async function submitCookieLogin(event) {
    event.preventDefault();
    const cookieInput = document.getElementById('cookieInput');
    const cookies = cookieInput.value.trim();

    if (!cookies) {
        showToast('Error', 'Please enter cookies', 'error');
        return;
    }

    let cookiesObj;
    try {
        cookiesObj = JSON.parse(cookies);
    } catch (e) {
        showToast('Error', 'Invalid JSON format', 'error');
        return;
    }

    try {
        const response = await api.post('/connectors/login', {
            platform: currentLoginPlatform,
            method: 'cookie',
            cookies: cookiesObj
        });

        if (response.data?.code === 0) {
            showToast('Success', 'Login successful!', 'success');
            bootstrap.Modal.getInstance(document.getElementById('loginModal')).hide();
            await loadAuthStatus();
        } else {
            showToast('Error', response.data?.message || 'Login failed', 'error');
        }
    } catch (error) {
        console.error('Login failed:', error);
        showToast('Error', error.response?.data?.message || 'Login failed', 'error');
    }
}

// Logout from platform
async function logoutPlatform(platform) {
    if (!confirm(`Are you sure you want to logout from ${platform}?`)) {
        return;
    }

    try {
        await api.post(`/connectors/logout/${platform}`);
        showToast('Success', 'Logged out successfully', 'success');
        await loadAuthStatus();
    } catch (error) {
        console.error('Logout failed:', error);
        showToast('Error', error.response?.data?.message || 'Logout failed', 'error');
    }
}

// Global variables for login state
let currentLoginPlatform = null;
let currentLoginMethod = null;
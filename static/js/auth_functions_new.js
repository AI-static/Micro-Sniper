
// ============ AUTH/LOGIN FUNCTIONS ============

// Load auth status for all platforms
async function loadAuthStatus() {
    const container = document.getElementById('authPlatformsList');
    container.innerHTML = `
        <div class="col-12">
            <div class="text-center py-5">
                <div class="spinner-border text-primary" role="status"></div>
                <p class="mt-3 text-muted">Checking login status...</p>
            </div>
        </div>
    `;

    try {
        const response = await api.get('/sniper/platforms');
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
                    <div class="auth-actions mb-3">
                        <button class="btn btn-primary w-100"
                                onclick="startCloudBrowserLogin('${platform.name}', '${platform.display_name}')">
                            <i class="bi bi-cloud-arrow-up"></i> Open Cloud Browser to Login
                        </button>
                    </div>
                    <div id="auth-detail-${platform.name}"></div>
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
        // Try to get context status - 这个接口需要后端实现
        const response = await api.get(`/connectors/context/${platform}`);
        const isLoggedIn = response.data?.data?.exists || false;

        if (isLoggedIn) {
            statusBadge.className = 'auth-status-badge status-logged-in';
            statusBadge.innerHTML = '<i class="bi bi-check-circle"></i> Logged In';
            detailDiv.innerHTML = `
                <div class="alert alert-success alert-sm mb-0">
                    <i class="bi bi-shield-check"></i> Login context is active
                    <div class="mt-2">
                        <small class="text-muted">Context expires in 24 hours</small>
                    </div>
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

// Start cloud browser login
async function startCloudBrowserLogin(platform, displayName) {
    const detailDiv = document.getElementById(`auth-detail-${platform}`);
    const statusBadge = document.getElementById(`status-${platform}`);

    // Show loading state
    detailDiv.innerHTML = `
        <div class="text-center py-3">
            <div class="spinner-border spinner-border-sm text-primary" role="status"></div>
            <p class="mt-2 mb-0 text-muted">
                <small>Starting cloud browser...</small>
            </p>
        </div>
    `;

    try {
        // Call login API - 后端会创建云浏览器并返回 URL
        const response = await api.post('/connectors/login', {
            platform: platform,
            method: 'qrcode'  // 即使是 qrcode，实际返回的是云浏览器 URL
        });

        if (response.data?.code === 0 && response.data?.data?.browser_url) {
            const browserUrl = response.data.data.browser_url;
            const timeout = response.data.data.timeout || 120;

            // 显示云浏览器链接
            detailDiv.innerHTML = `
                <div class="cloud-browser-instructions">
                    <div class="alert alert-info mb-3">
                        <h6 class="alert-heading"><i class="bi bi-info-circle"></i> How to Login:</h6>
                        <ol class="mb-0 small">
                            <li>Click the button below to open cloud browser</li>
                            <li>Complete login in the cloud browser</li>
                            <li>Come back here - we'll auto-detect when you're done</li>
                        </ol>
                    </div>

                    <div class="d-grid gap-2 mb-3">
                        <button class="btn btn-success btn-lg" onclick="openCloudBrowser('${browserUrl}')">
                            <i class="bi bi-box-arrow-up-right"></i> Open Cloud Browser
                            <br><small>Login within ${timeout} seconds</small>
                        </button>
                        <a href="${browserUrl}" target="_blank" class="btn btn-outline-secondary">
                            <i class="bi bi-link-45deg"></i> Copy URL
                        </a>
                    </div>

                    <div class="text-center text-muted">
                        <small>
                            <i class="bi bi-hourglass-split"></i>
                            Waiting for you to complete login...
                        </small>
                    </div>

                    <!-- Auto-refresh countdown -->
                    <div class="mt-3">
                        <div class="progress" style="height: 6px;">
                            <div id="login-progress-${platform}" class="progress-bar progress-bar-striped progress-bar-animated" style="width: 100%"></div>
                        </div>
                        <small class="text-muted" id="login-countdown-${platform}">
                            ${timeout}s remaining
                        </small>
                    </div>
                </div>
            `;

            // Start countdown
            let remaining = timeout;
            const countdownInterval = setInterval(() => {
                remaining--;
                const progressPercent = (remaining / timeout) * 100;
                document.getElementById(`login-progress-${platform}`).style.width = progressPercent + '%';
                document.getElementById(`login-countdown-${platform}`).textContent = `${remaining}s remaining`;

                if (remaining <= 0) {
                    clearInterval(countdownInterval);
                    detailDiv.innerHTML = `
                        <div class="alert alert-warning">
                            <i class="bi bi-clock-history"></i> Login session expired. Please try again.
                        </div>
                    `;
                }
            }, 1000);

            // Start polling for login status
            const pollInterval = setInterval(async () => {
                const loggedIn = await checkLoginSync(platform);
                if (loggedIn) {
                    clearInterval(countdownInterval);
                    clearInterval(pollInterval);
                    await checkPlatformLoginStatus(platform);
                    showToast('Success', `${displayName} login successful!`, 'success');
                }
            }, 3000);  // Check every 3 seconds

            // Auto-stop polling after timeout
            setTimeout(() => {
                clearInterval(pollInterval);
            }, timeout * 1000);

        } else {
            detailDiv.innerHTML = `
                <div class="alert alert-danger">
                    <i class="bi bi-exclamation-triangle"></i>
                    ${response.data?.message || 'Failed to start cloud browser'}
                </div>
            `;
        }

    } catch (error) {
        console.error('Failed to start cloud browser:', error);
        detailDiv.innerHTML = `
            <div class="alert alert-danger">
                <i class="bi bi-exclamation-triangle"></i>
                ${error.response?.data?.message || 'Failed to start cloud browser'}
            </div>
        `;
    }
}

// Open cloud browser in new tab
function openCloudBrowser(url) {
    window.open(url, '_blank', 'noopener,noreferrer');
    showToast('Info', 'Cloud browser opened! Complete login there and come back.', 'info');
}

// Synchronous check if logged in (for polling)
async function checkLoginSync(platform) {
    try {
        const response = await api.get(`/connectors/context/${platform}`);
        return response.data?.data?.exists || false;
    } catch (error) {
        return false;
    }
}

// Global state
let loginPollIntervals = {};

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
                                id="loginBtn-${platform.name}"
                                onclick="startCloudBrowserLogin('${platform.name}', '${platform.display_name}')">
                            <i class="bi bi-box-arrow-in-right"></i> Login to ${platform.display_name}
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
    const loginBtn = document.getElementById(`loginBtn-${platform}`);

    try {
        // Try to get context status
        const response = await api.get(`/connectors/context/${platform}`);
        const isLoggedIn = response.data?.data?.exists || false;

        if (isLoggedIn) {
            statusBadge.className = 'auth-status-badge status-logged-in';
            statusBadge.innerHTML = '<i class="bi bi-check-circle"></i> Logged In';
            if (loginBtn) {
                loginBtn.disabled = true;
                loginBtn.innerHTML = '<i class="bi bi-check-circle"></i> Already Logged In';
            }
            detailDiv.innerHTML = `
                <div class="alert alert-success alert-sm mb-0">
                    <i class="bi bi-shield-check"></i> Login context is active
                    <div class="mt-2">
                        <small class="text-muted">You can now create tasks for this platform</small>
                    </div>
                </div>
            `;
        } else {
            statusBadge.className = 'auth-status-badge status-logged-out';
            statusBadge.innerHTML = '<i class="bi bi-x-circle"></i> Not Logged In';
            if (loginBtn) {
                loginBtn.disabled = false;
            }
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
    const loginBtn = document.getElementById(`loginBtn-${platform}`);

    // Show loading state
    loginBtn.disabled = true;
    loginBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Starting...';

    detailDiv.innerHTML = `
        <div class="text-center py-3">
            <div class="spinner-border spinner-border-sm text-primary" role="status"></div>
            <p class="mt-2 mb-0 text-muted">
                <small>Creating cloud browser session...</small>
            </p>
        </div>
    `;

    try {
        // Call login API - 后端会创建云浏览器并返回 URL
        const response = await api.post('/connectors/login', {
            platform: platform,
            method: 'qrcode'
        });

        if (response.data?.code === 0 && response.data?.data) {
            const data = response.data.data;
            const browserUrl = data.browser_url || data.qrcode;  // 兼容两种返回
            const contextId = data.context_id;
            const timeout = data.timeout || 120;

            // 保存当前登录信息
            window.currentLogin = {
                platform: platform,
                contextId: contextId,
                timeout: timeout
            };

            // 显示云浏览器引导
            detailDiv.innerHTML = `
                <div class="cloud-browser-guide">
                    <div class="alert alert-info mb-3">
                        <h6 class="alert-heading"><i class="bi bi-info-circle"></i> Login Instructions:</h6>
                        <ol class="mb-0 small">
                            <li><strong>Click "Open Cloud Browser" below</strong> - opens in new tab</li>
                            <li>Complete login in the cloud browser (scan QR code or enter password)</li>
                            <li><strong>Come back here</strong> and click "I've Logged In"</li>
                        </ol>
                    </div>

                    <div class="d-grid gap-2 mb-3">
                        <button class="btn btn-success btn-lg"
                                onclick="openCloudBrowser('${browserUrl}')">
                            <i class="bi bi-box-arrow-up-right"></i> Open Cloud Browser
                        </button>
                    </div>

                    <div class="text-center mb-3">
                        <small class="text-muted">
                            Context ID: <code>${contextId}</code><br>
                            Expires in: <strong>${timeout} seconds</strong>
                        </small>
                    </div>

                    <div class="d-grid gap-2">
                        <button class="btn btn-primary"
                                onclick="confirmLoginCompleted('${platform}', '${contextId}')">
                            <i class="bi bi-check-circle"></i> I've Logged In - Save Context
                        </button>
                        <button class="btn btn-outline-secondary btn-sm"
                                onclick="cancelLogin('${platform}')">
                            Cancel
                        </button>
                    </div>

                    <!-- 倒计时进度条 -->
                    <div class="mt-3">
                        <div class="progress" style="height: 8px;">
                            <div id="login-progress-${platform}" class="progress-bar progress-bar-striped progress-bar-animated bg-warning" style="width: 100%"></div>
                        </div>
                        <div class="text-center mt-1">
                            <small class="text-muted" id="login-countdown-${platform}">
                                ${timeout}s remaining
                            </small>
                        </div>
                    </div>
                </div>
            `;

            // Start countdown
            startCountdown(platform, timeout);

        } else {
            throw new Error(response.data?.message || 'Failed to start cloud browser');
        }

    } catch (error) {
        console.error('Failed to start cloud browser:', error);
        detailDiv.innerHTML = `
            <div class="alert alert-danger">
                <i class="bi bi-exclamation-triangle"></i>
                ${error.response?.data?.message || error.message || 'Failed to start cloud browser'}
            </div>
        `;
        loginBtn.disabled = false;
        loginBtn.innerHTML = `<i class="bi bi-box-arrow-in-right"></i> Login to ${displayName}`;
    }
}

// Open cloud browser in new tab
function openCloudBrowser(url) {
    window.open(url, '_blank', 'noopener,noreferrer');
    showToast('Info', 'Cloud browser opened! Complete login there, then come back.', 'info');
}

// Start countdown timer
function startCountdown(platform, timeout) {
    let remaining = timeout;
    const countdownInterval = setInterval(() => {
        remaining--;
        const progressPercent = (remaining / timeout) * 100;

        const progressBar = document.getElementById(`login-progress-${platform}`);
        const countdownText = document.getElementById(`login-countdown-${platform}`);

        if (progressBar) progressBar.style.width = progressPercent + '%';
        if (countdownText) countdownText.textContent = `${remaining}s remaining`;

        if (remaining <= 0) {
            clearInterval(countdownInterval);
            if (progressBar) {
                progressBar.classList.remove('progress-bar-animated');
                progressBar.classList.add('bg-danger');
            }
            if (countdownText) {
                countdownText.textContent = 'Expired';
                countdownText.classList.add('text-danger');
            }

            // Show expired message
            const detailDiv = document.getElementById(`auth-detail-${platform}`);
            if (detailDiv) {
                detailDiv.innerHTML += `
                    <div class="alert alert-danger mt-2">
                        <i class="bi bi-clock-history"></i> Session expired. Please try again.
                    </div>
                `;
            }
        }
    }, 1000);

    // Save interval ID for cleanup
    if (!window.loginTimers) window.loginTimers = {};
    window.loginTimers[platform] = countdownInterval;
}

// User confirms they've completed login
async function confirmLoginCompleted(platform, contextId) {
    const detailDiv = document.getElementById(`auth-detail-${platform}`);

    // Show saving state
    detailDiv.innerHTML += `
        <div class="text-center py-2" id="saving-context">
            <div class="spinner-border spinner-border-sm text-primary" role="status"></div>
            <p class="mt-1 mb-0 text-muted"><small>Saving login context...</small></p>
        </div>
    `;

    try {
        // Call backend to save context
        const response = await api.post(`/connectors/login/${platform}/confirm`, {
            context_id: contextId
        });

        if (response.data?.code === 0) {
            // Clean up countdown
            if (window.loginTimers && window.loginTimers[platform]) {
                clearInterval(window.loginTimers[platform]);
            }

            showToast('Success', 'Login context saved successfully!', 'success');
            await checkPlatformLoginStatus(platform);
        } else {
            throw new Error(response.data?.message || 'Failed to save context');
        }

    } catch (error) {
        console.error('Failed to save context:', error);
        showToast('Error', error.response?.data?.message || error.message || 'Failed to save context', 'error');

        // Remove saving indicator
        const savingDiv = document.getElementById('saving-context');
        if (savingDiv) savingDiv.remove();
    }
}

// Cancel login
function cancelLogin(platform) {
    // Clean up countdown
    if (window.loginTimers && window.loginTimers[platform]) {
        clearInterval(window.loginTimers[platform]);
    }

    // Reset UI
    const detailDiv = document.getElementById(`auth-detail-${platform}`);
    const loginBtn = document.getElementById(`loginBtn-${platform}`);

    if (detailDiv) detailDiv.innerHTML = '';
    if (loginBtn) {
        loginBtn.disabled = false;
        loginBtn.innerHTML = `<i class="bi bi-box-arrow-in-right"></i> Login`;
    }

    showToast('Info', 'Login cancelled', 'info');
}

// Global state
window.loginTimers = {};
window.currentLogin = null;
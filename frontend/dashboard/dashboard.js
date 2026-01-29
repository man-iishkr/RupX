// dashboard.js - CORRECTED VERSION


// API Configuration
const API_BASE_URL = 'https://rupx-backend.onrender.com/api';  

// Current user and project (shared state)
window.currentUser = null;
window.activeProject = null;

// Load user info on dashboard pages
async function loadUserInfo() {
    try {
        const response = await fetch(`${API_BASE_URL}/auth/status`, {
            credentials: 'include'
        });
        
        if (!response.ok) {
            window.location.href = '/auth/login.html';
            return;
        }
        
        const data = await response.json();
        window.currentUser = data.user;
        
        // Update UI if user name element exists
        const userNameElement = document.getElementById('user-name');
        if (userNameElement) {
            userNameElement.textContent = data.user.name || data.user.email;
        }
        
    } catch (error) {
        console.error('Failed to load user info:', error);
        window.location.href = '/auth/login.html';
    }
}

// Logout function
function logout() {
    fetch(`${API_BASE_URL}/auth/logout`, {
        method: 'POST',
        credentials: 'include'
    })
    .then(() => {
        window.location.href = '/landing/index.html';
    })
    .catch((error) => {
        console.error('Logout error:', error);
        // Redirect anyway
        window.location.href = '/landing/index.html';
    });
}

// Alert helper function (for pages that need it)
function showAlert(message, type = 'info') {
    // Simple alert for now - you can enhance this
    console.log(`[${type.toUpperCase()}] ${message}`);
    alert(message);
}

// Initialize dashboard (call this on dashboard pages)
function initializeDashboard() {
    loadUserInfo();
}

// Auto-initialize if we're on a dashboard page
if (window.location.pathname.includes('/dashboard/')) {
    document.addEventListener('DOMContentLoaded', () => {
        loadUserInfo();
    });
}
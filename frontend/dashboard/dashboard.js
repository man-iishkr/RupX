// Common Dashboard Functions
const API_BASE = 'https://rupx-backend.onrender.com/api';

// Check authentication on load
window.addEventListener('DOMContentLoaded', async () => {
    await checkAuth();
});

// Check if user is authenticated
async function checkAuth() {
    try {
        const response = await fetch(`${API_BASE}/auth/status`, {
            credentials: 'include'
        });
        
        const data = await response.json();
        
        if (!data.authenticated) {
            window.location.href = '../auth/login.html';
        }
    } catch (error) {
        console.error('Auth check failed:', error);
        window.location.href = '../auth/login.html';
    }
}

// Logout function
async function logout() {
    try {
        const response = await fetch(`${API_BASE}/auth/logout`, {
            method: 'POST',
            credentials: 'include'
        });
        
        // Clear any local data
        sessionStorage.clear();
        localStorage.clear();
        
        // Redirect to login
        window.location.href = '../landing/index.html';
    } catch (error) {
        console.error('Logout failed:', error);
        // Force redirect anyway
        window.location.href = '../landing/index.html';
    }
}

// Show alert message
function showAlert(message, type = 'success') {
    const alertDiv = document.createElement('div');
    alertDiv.className = `alert alert-${type}`;
    alertDiv.innerHTML = `
        <span>${type === 'success' ? '✓' : type === 'error' ? '✗' : '⚠'}</span>
        <span>${message}</span>
    `;
    
    const content = document.querySelector('.main-content');
    content.insertBefore(alertDiv, content.firstChild);
    
    setTimeout(() => {
        alertDiv.remove();
    }, 5000);
}

// Format date
function formatDate(dateString) {
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric'
    });
}

// Format time
function formatTime(seconds) {
    if (!seconds) return 'N/A';
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}m ${secs}s`;
}
// API Base URL
const API_BASE = 'https://rupx-backend.onrender.com/api';

// Show error message
function showError(message) {
    const errorEl = document.getElementById('error-message');
    errorEl.textContent = message;
    errorEl.classList.add('show');
}

// Hide error message
function hideError() {
    const errorEl = document.getElementById('error-message');
    errorEl.classList.remove('show');
}

// Handle Signup
const signupForm = document.getElementById('signup-form');
if (signupForm) {
    signupForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        hideError();
        
        const email = document.getElementById('email').value;
        const password = document.getElementById('password').value;
        const confirmPassword = document.getElementById('confirm-password').value;
        
        // Validation
        if (password !== confirmPassword) {
            showError('Passwords do not match');
            return;
        }
        
        if (password.length < 8) {
            showError('Password must be at least 8 characters');
            return;
        }
        
        // Disable button
        const btn = signupForm.querySelector('button');
        btn.disabled = true;
        btn.textContent = 'Creating account...';
        
        try {
            const response = await fetch(`${API_BASE}/auth/signup`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                credentials: 'include',
                body: JSON.stringify({ email, password })
            });
            
            const data = await response.json();
            
            if (response.ok) {
                // Success - redirect to dashboard
                window.location.href = '../dashboard/projects.html';
            } else {
                showError(data.error || 'Signup failed');
                btn.disabled = false;
                btn.textContent = 'Create Account';
            }
        } catch (error) {
            showError('Network error. Please try again.');
            btn.disabled = false;
            btn.textContent = 'Create Account';
        }
    });
}

// Handle Login
const loginForm = document.getElementById('login-form');
if (loginForm) {
    loginForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        hideError();
        
        const email = document.getElementById('email').value;
        const password = document.getElementById('password').value;
        
        // Disable button
        const btn = loginForm.querySelector('button');
        btn.disabled = true;
        btn.textContent = 'Signing in...';
        
        try {
            const response = await fetch(`${API_BASE}/auth/login`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                credentials: 'include',
                body: JSON.stringify({ email, password })
            });
            
            const data = await response.json();
            
            if (response.ok) {
                // Success - redirect to dashboard
                window.location.href = '../dashboard/projects.html';
            } else {
                showError(data.error || 'Login failed');
                btn.disabled = false;
                btn.textContent = 'Sign In';
            }
        } catch (error) {
            showError('Network error. Please try again.');
            btn.disabled = false;
            btn.textContent = 'Sign In';
        }
    });
}
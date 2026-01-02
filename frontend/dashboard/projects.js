// Projects Management
// const API_BASE = "http://127.0.0.1:5000/api";
let projects = [];

// Helper function to format the date (FIXED: Added missing function)
function formatDate(dateString) {
    if (!dateString) return 'N/A';
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric'
    });
}

// Load projects on page load
window.addEventListener('DOMContentLoaded', async () => {
    await loadProjects();
});

// Load all projects
async function loadProjects() {
    try {
        const response = await fetch(`${API_BASE}/auth/projects`, {
            credentials: 'include'
        });
        
        const data = await response.json();
        projects = data.projects || [];
        
        displayProjects();
    } catch (error) {
        console.error('Failed to load projects:', error);
        showAlert('Failed to load projects', 'error');
    }
}

// Display projects
function displayProjects() {
    const grid = document.getElementById('projects-grid');
    
    if (projects.length === 0) {
        grid.innerHTML = `
            <div style="grid-column: 1/-1; text-align: center; padding: 4rem; color: var(--text-secondary);">
                <div style="font-size: 4rem; margin-bottom: 1rem;">📁</div>
                <h3>No projects yet</h3>
                <p>Create your first project to get started</p>
            </div>
        `;
        return;
    }
    
    grid.innerHTML = projects.map(project => `
        <div class="project-card ${project.is_active ? 'active' : ''}" onclick="activateProject(${project.id})">
            <div class="project-header">
                <div class="project-name">${project.name}</div>
                ${project.is_active ? '<div class="project-badge active">Active</div>' : ''}
            </div>
            <div class="project-info">
                <div class="info-item">
                    <span class="status-indicator ${project.dataset_uploaded ? 'success' : ''}"></span>
                    <span>Dataset ${project.dataset_uploaded ? 'Uploaded' : 'Not Uploaded'}</span>
                </div>
                <div class="info-item">
                    <span class="status-indicator ${project.model_trained ? 'success' : ''}"></span>
                    <span>Model ${project.model_trained ? 'Trained' : 'Not Trained'}</span>
                </div>
                <div class="info-item">
                    <span>📅</span>
                    <span>${formatDate(project.created_at)}</span>
                </div>
            </div>
            <div class="project-actions">
                <button class="btn-icon" onclick="event.stopPropagation(); deleteProject(${project.id})" title="Delete">
                    🗑️
                </button>
            </div>
        </div>
    `).join('');
}

// Show create modal
function showCreateModal() {
    if (projects.length >= 5) {
        showAlert('Maximum 5 projects allowed', 'warning');
        return;
    }
    
    const modal = document.getElementById('create-modal');
    modal.classList.add('show');
}

// Hide create modal
function hideCreateModal() {
    const modal = document.getElementById('create-modal');
    modal.classList.remove('show');
    document.getElementById('create-form').reset();
}

// Create new project
document.getElementById('create-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const name = document.getElementById('project-name').value.trim();
    
    if (!name) {
        showAlert('Project name required', 'error');
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE}/auth/projects/create`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            credentials: 'include',
            body: JSON.stringify({ name })
        });
        
        const data = await response.json();
        
        if (response.ok) {
            showAlert('Project created successfully', 'success');
            hideCreateModal();
            await loadProjects();
        } else {
            // Note: 409 Conflict usually means a project with this name already exists
            showAlert(data.error || 'Failed to create project', 'error');
        }
    } catch (error) {
        console.error('Create project error:', error);
        showAlert('Network error', 'error');
    }
});

// Activate project
async function activateProject(projectId) {
    try {
        const response = await fetch(`${API_BASE}/auth/projects/${projectId}/activate`, {
            method: 'POST',
            credentials: 'include'
        });
        
        if (response.ok) {
            showAlert('Project activated', 'success');
            await loadProjects();
        } else {
            showAlert('Failed to activate project', 'error');
        }
    } catch (error) {
        console.error('Activate error:', error);
        showAlert('Network error', 'error');
    }
}

// Delete project
async function deleteProject(projectId) {
    if (!confirm('Are you sure you want to delete this project? This cannot be undone.')) {
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE}/auth/projects/${projectId}`, {
            method: 'DELETE',
            credentials: 'include'
        });
        
        if (response.ok) {
            showAlert('Project deleted', 'success');
            await loadProjects();
        } else {
            showAlert('Failed to delete project', 'error');
        }
    } catch (error) {
        console.error('Delete error:', error);
        showAlert('Network error', 'error');
    }
}

// Close modal on outside click
function handleModalClick(event) {
    if (event.target.id === 'create-modal') {
        hideCreateModal();
    }
}

function showAlert(message, type = 'info') {
    alert(message);
}
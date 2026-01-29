// projects.js 


const API_BASE_URL = 'https://rupx-backend.onrender.com/api';  

let projects = [];

// Load projects on page load
async function loadProjects() {
    try {
        const response = await fetch(`${API_BASE_URL}/auth/projects`, {  
            credentials: 'include'
        });
        
        if (!response.ok) {
            throw new Error('Failed to load projects');
        }
        
        const data = await response.json();
        projects = data.projects || [];
        
        displayProjects(projects);
        
        // Update active project
        const active = projects.find(p => p.is_active);
        if (active) {
            window.activeProject = active;
        }
        
    } catch (error) {
        console.error('Failed to load projects:', error);
        showAlert('Failed to load projects. Please refresh the page.', 'error');
    }
}

function displayProjects(projectsList) {
    const container = document.getElementById('projects-list');
    
    if (!container) {
        console.warn('Projects list container not found');
        return;
    }
    
    container.innerHTML = '';
    
    if (!projectsList || projectsList.length === 0) {
        container.innerHTML = '<p style="text-align: center; color: #666; padding: 2rem;">No projects yet. Create your first project!</p>';
        return;
    }
    
    projectsList.forEach(project => {
        const card = document.createElement('div');
        card.className = 'project-card';
        card.innerHTML = `
            <div class="project-header">
                <h3>${escapeHtml(project.name)}</h3>
                ${project.is_active ? '<span class="badge badge-active">Active</span>' : ''}
            </div>
            <div class="project-info">
                <p><strong>Mode:</strong> ${escapeHtml(project.attendance_mode || 'Face Recognition')}</p>
                <p><strong>Dataset:</strong> ${project.dataset_uploaded ? '✅ Uploaded' : '❌ Not uploaded'}</p>
                <p><strong>Model:</strong> ${project.model_trained ? '✅ Trained' : '❌ Not trained'}</p>
                <p><strong>Created:</strong> ${formatDate(project.created_at)}</p>
            </div>
            <div class="project-actions">
                ${!project.is_active ? 
                    `<button onclick="activateProject(${project.id})" class="btn btn-primary">Activate</button>` : 
                    '<button class="btn btn-secondary" disabled>Active</button>'
                }
                <button onclick="deleteProject(${project.id}, '${escapeHtml(project.name)}')" class="btn btn-danger">Delete</button>
            </div>
        `;
        container.appendChild(card);
    });
}

// Create project
async function createProject(event) {
    event.preventDefault();
    
    const nameInput = document.getElementById('project-name');
    const modeSelect = document.getElementById('attendance-mode');
    
    if (!nameInput || !modeSelect) {
        console.error('Form elements not found');
        return;
    }
    
    const name = nameInput.value.trim();
    const mode = modeSelect.value;
    
    if (!name) {
        showAlert('Please enter a project name', 'warning');
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE_URL}/auth/projects/create`, {  // FIXED: Correct path
            method: 'POST',
            credentials: 'include',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                name: name,
                attendance_mode: mode 
            })
        });
        
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.error || 'Failed to create project');
        }
        
        showAlert('Project created successfully!', 'success');
        
        // Reset form
        nameInput.value = '';
        modeSelect.value = 'face_recognition';
        
        // Reload projects
        await loadProjects();
        
    } catch (error) {
        console.error('Create project error:', error);
        showAlert(`Failed to create project: ${error.message}`, 'error');
    }
}

// Activate project
async function activateProject(projectId) {
    try {
        const response = await fetch(`${API_BASE_URL}/auth/projects/${projectId}/activate`, {  // FIXED: Correct path
            method: 'POST',
            credentials: 'include'
        });
        
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.error || 'Failed to activate project');
        }
        
        showAlert('Project activated!', 'success');
        await loadProjects();
        
    } catch (error) {
        console.error('Activate project error:', error);
        showAlert(`Failed to activate project: ${error.message}`, 'error');
    }
}

// Delete project
async function deleteProject(projectId, projectName) {
    if (!confirm(`Are you sure you want to delete "${projectName}"? This cannot be undone.`)) {
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE_URL}/auth/projects/${projectId}`, {  // FIXED: Correct path
            method: 'DELETE',
            credentials: 'include'
        });
        
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.error || 'Failed to delete project');
        }
        
        showAlert('Project deleted successfully', 'success');
        await loadProjects();
        
    } catch (error) {
        console.error('Delete project error:', error);
        showAlert(`Failed to delete project: ${error.message}`, 'error');
    }
}

// Helper functions
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function formatDate(dateString) {
    if (!dateString) return 'Unknown';
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', { 
        year: 'numeric', 
        month: 'short', 
        day: 'numeric' 
    });
}

function showAlert(message, type = 'info') {
    console.log(`[${type.toUpperCase()}] ${message}`);
    
    // You can enhance this with a better UI alert
    alert(message);
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    loadProjects();
    
    // Attach form handler if form exists
    const createForm = document.getElementById('create-project-form');
    if (createForm) {
        createForm.addEventListener('submit', createProject);
    }
});
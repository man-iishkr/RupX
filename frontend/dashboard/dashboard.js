// dashboard.js - Complete file with client-side training
// Keep all your existing UI code, just modify training section

let currentProject = null;
let mlClient = null;

// Load projects on page load
async function loadProjects() {
    try {
        const response = await fetch(`${API_BASE_URL}/api/auth/projects`, {
            credentials: 'include'
        });
        
        const data = await response.json();
        
        if (data.projects) {
            displayProjects(data.projects);
            
            const active = data.projects.find(p => p.is_active);
            if (active) {
                currentProject = active;
                document.getElementById('active-project-section').classList.remove('hidden');
            }
        }
    } catch (error) {
        console.error('Failed to load projects:', error);
    }
}

function displayProjects(projects) {
    const container = document.getElementById('projects-list');
    container.innerHTML = '';
    
    projects.forEach(project => {
        const card = document.createElement('div');
        card.className = 'project-card';
        card.innerHTML = `
            <h3>${project.name}</h3>
            <p>Mode: ${project.attendance_mode}</p>
            <p>Dataset: ${project.dataset_uploaded ? '✅' : '❌'}</p>
            <p>Model: ${project.model_trained ? '✅' : '❌'}</p>
            ${project.is_active ? '<span class="badge">Active</span>' : ''}
            <button onclick="activateProject(${project.id})">
                ${project.is_active ? 'Active' : 'Activate'}
            </button>
            <button onclick="deleteProject(${project.id})">Delete</button>
        `;
        container.appendChild(card);
    });
}

// Create project
document.getElementById('create-project-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const name = document.getElementById('project-name').value;
    const mode = document.getElementById('attendance-mode').value;
    
    try {
        const response = await fetch(`${API_BASE_URL}/api/auth/projects/create`, {
            method: 'POST',
            credentials: 'include',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, attendance_mode: mode })
        });
        
        if (response.ok) {
            loadProjects();
            document.getElementById('create-project-form').reset();
        }
    } catch (error) {
        alert('Failed to create project');
    }
});

// Upload dataset
document.getElementById('upload-btn').addEventListener('click', async () => {
    const fileInput = document.getElementById('dataset-file');
    const file = fileInput.files[0];
    
    if (!file) {
        alert('Please select a ZIP file');
        return;
    }
    
    const formData = new FormData();
    formData.append('file', file);
    
    try {
        const response = await fetch(`${API_BASE_URL}/api/dataset/upload`, {
            method: 'POST',
            credentials: 'include',
            body: formData
        });
        
        const data = await response.json();
        
        if (response.ok) {
            document.getElementById('upload-status').innerHTML = `
                ✅ Uploaded successfully!<br>
                Persons: ${data.stats.total_persons}<br>
                Images: ${data.stats.total_images}
            `;
            loadProjects();
        } else {
            document.getElementById('upload-status').innerHTML = 
                `❌ Error: ${data.error}`;
        }
    } catch (error) {
        alert('Upload failed');
    }
});

// Train model - MODIFIED FOR CLIENT-SIDE ML
document.getElementById('train-btn').addEventListener('click', async () => {
    try {
        document.getElementById('train-btn').disabled = true;
        document.getElementById('training-progress').innerHTML = 
            '<p>Loading ML models in browser...</p>';
        
        // Initialize ML Client
        if (!mlClient) {
            mlClient = new MLClient();
            const result = await mlClient.initialize((progress) => {
                document.getElementById('training-progress').innerHTML = `
                    <p>${progress.message}</p>
                    <div class="progress-bar">
                        <div style="width: ${progress.progress}%; height: 20px; background: #4CAF50;"></div>
                    </div>
                `;
            });
            
            if (!result.success) {
                alert('Failed to load ML models: ' + result.error);
                document.getElementById('train-btn').disabled = false;
                return;
            }
        }
        
        // Get dataset from backend
        const response = await fetch(`${API_BASE_URL}/api/train/start`, {
            method: 'POST',
            credentials: 'include'
        });
        
        const data = await response.json();
        
        if (!response.ok) {
            alert(data.error || 'Failed to start training');
            document.getElementById('train-btn').disabled = false;
            return;
        }
        
        // Train in browser
        document.getElementById('training-progress').innerHTML = 
            '<p>Training in browser... This may take 1-3 minutes.</p>';
        
        const embeddings = await mlClient.trainFromDataset(data.dataset, (progress) => {
            document.getElementById('training-progress').innerHTML = `
                <p>${progress.message}</p>
                <div class="progress-bar">
                    <div style="width: ${progress.progress}%; height: 20px; background: #4CAF50;"></div>
                </div>
                ${progress.person ? `<p>Processing: ${progress.person}</p>` : ''}
            `;
        });
        
        // Send embeddings to backend
        const saveResponse = await fetch(`${API_BASE_URL}/api/train/save`, {
            method: 'POST',
            credentials: 'include',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                embeddings: embeddings,
                metadata: {
                    model: 'mobilenet_tfjs',
                    total_images_processed: data.dataset.total_images
                }
            })
        });
        
        const saveData = await saveResponse.json();
        
        if (saveData.success) {
            document.getElementById('training-progress').innerHTML = 
                '<p>✅ Training completed successfully!</p>';
            loadProjects();
        } else {
            alert('Failed to save model: ' + saveData.error);
        }
        
    } catch (error) {
        console.error('Training error:', error);
        alert('Training failed: ' + error.message);
    } finally {
        document.getElementById('train-btn').disabled = false;
    }
});

// Start recognition
document.getElementById('start-recognition-btn').addEventListener('click', () => {
    window.location.href = 'recognize.html';
});

// Download attendance
document.getElementById('download-attendance-btn').addEventListener('click', async () => {
    try {
        const response = await fetch(`${API_BASE_URL}/api/attendance/download`, {
            credentials: 'include'
        });
        
        if (response.ok) {
            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = 'attendance.xlsx';
            a.click();
        }
    } catch (error) {
        alert('Failed to download attendance');
    }
});

// Activate project
async function activateProject(projectId) {
    try {
        const response = await fetch(`${API_BASE_URL}/api/auth/projects/${projectId}/activate`, {
            method: 'POST',
            credentials: 'include'
        });
        
        if (response.ok) {
            loadProjects();
        }
    } catch (error) {
        alert('Failed to activate project');
    }
}

// Delete project
async function deleteProject(projectId) {
    if (!confirm('Are you sure you want to delete this project?')) {
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE_URL}/api/auth/projects/${projectId}`, {
            method: 'DELETE',
            credentials: 'include'
        });
        
        if (response.ok) {
            loadProjects();
        }
    } catch (error) {
        alert('Failed to delete project');
    }
}

// Logout
document.getElementById('logout-btn').addEventListener('click', async () => {
    await fetch(`${API_BASE_URL}/api/auth/logout`, {
        method: 'POST',
        credentials: 'include'
    });
    window.location.href = 'index.html';
});

// Initialize on load
window.addEventListener('load', () => {
    loadProjects();
});
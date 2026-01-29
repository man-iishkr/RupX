// dashboard.js - Complete file with client-side training
// FIXED: Added null checks and corrected API paths

const API_BASE_URL = 'https://rupx-backend.onrender.com/api';

let currentProject = null;
let mlClient = null;

// Load projects on page load
async function loadProjects() {
    try {
        const response = await fetch(`${API_BASE_URL}/auth/projects`, {  // FIXED: Removed duplicate /api
            credentials: 'include'
        });
        
        const data = await response.json();
        
        if (data.projects) {
            displayProjects(data.projects);
            
            const active = data.projects.find(p => p.is_active);
            if (active) {
                currentProject = active;
                const activeSection = document.getElementById('active-project-section');
                if (activeSection) {
                    activeSection.classList.remove('hidden');
                }
            }
        }
    } catch (error) {
        console.error('Failed to load projects:', error);
    }
}

function displayProjects(projects) {
    const container = document.getElementById('projects-list');
    if (!container) return;  // FIXED: Added null check
    
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

// Create project - FIXED: Added null check
const createProjectForm = document.getElementById('create-project-form');
if (createProjectForm) {
    createProjectForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const name = document.getElementById('project-name').value;
        const mode = document.getElementById('attendance-mode').value;
        
        try {
            const response = await fetch(`${API_BASE_URL}/auth/projects/create`, {  // FIXED: Removed duplicate /api
                method: 'POST',
                credentials: 'include',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name, attendance_mode: mode })
            });
            
            if (response.ok) {
                loadProjects();
                createProjectForm.reset();
            }
        } catch (error) {
            alert('Failed to create project');
        }
    });
}

// Upload dataset - FIXED: Added null check
const uploadBtn = document.getElementById('upload-btn');
if (uploadBtn) {
    uploadBtn.addEventListener('click', async () => {
        const fileInput = document.getElementById('dataset-file');
        const file = fileInput?.files[0];
        
        if (!file) {
            alert('Please select a ZIP file');
            return;
        }
        
        const formData = new FormData();
        formData.append('file', file);
        
        try {
            const response = await fetch(`${API_BASE_URL}/dataset/upload`, {  // FIXED: Removed duplicate /api
                method: 'POST',
                credentials: 'include',
                body: formData
            });
            
            const data = await response.json();
            
            const uploadStatus = document.getElementById('upload-status');
            if (uploadStatus) {
                if (response.ok) {
                    uploadStatus.innerHTML = `
                        ✅ Uploaded successfully!<br>
                        Persons: ${data.stats.total_persons}<br>
                        Images: ${data.stats.total_images}
                    `;
                    loadProjects();
                } else {
                    uploadStatus.innerHTML = `❌ Error: ${data.error}`;
                }
            }
        } catch (error) {
            alert('Upload failed');
        }
    });
}

// Train model - MODIFIED FOR CLIENT-SIDE ML - FIXED: Added null check
const trainBtn = document.getElementById('train-btn');
if (trainBtn) {
    trainBtn.addEventListener('click', async () => {
        try {
            trainBtn.disabled = true;
            const trainingProgress = document.getElementById('training-progress');
            if (trainingProgress) {
                trainingProgress.innerHTML = '<p>Loading ML models in browser...</p>';
            }
            
            // Initialize ML Client
            if (!mlClient) {
                mlClient = new MLClient();
                const result = await mlClient.initialize((progress) => {
                    if (trainingProgress) {
                        trainingProgress.innerHTML = `
                            <p>${progress.message}</p>
                            <div class="progress-bar">
                                <div style="width: ${progress.progress}%; height: 20px; background: #4CAF50;"></div>
                            </div>
                        `;
                    }
                });
                
                if (!result.success) {
                    alert('Failed to load ML models: ' + result.error);
                    trainBtn.disabled = false;
                    return;
                }
            }
            
            // Get dataset from backend
            const response = await fetch(`${API_BASE_URL}/train/start`, {  // FIXED: Removed duplicate /api
                method: 'POST',
                credentials: 'include'
            });
            
            const data = await response.json();
            
            if (!response.ok) {
                alert(data.error || 'Failed to start training');
                trainBtn.disabled = false;
                return;
            }
            
            // Train in browser
            if (trainingProgress) {
                trainingProgress.innerHTML = '<p>Training in browser... This may take 1-3 minutes.</p>';
            }
            
            const embeddings = await mlClient.trainFromDataset(data.dataset, (progress) => {
                if (trainingProgress) {
                    trainingProgress.innerHTML = `
                        <p>${progress.message}</p>
                        <div class="progress-bar">
                            <div style="width: ${progress.progress}%; height: 20px; background: #4CAF50;"></div>
                        </div>
                        ${progress.person ? `<p>Processing: ${progress.person}</p>` : ''}
                    `;
                }
            });
            
            // Send embeddings to backend
            const saveResponse = await fetch(`${API_BASE_URL}/train/save`, {  // FIXED: Removed duplicate /api
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
                if (trainingProgress) {
                    trainingProgress.innerHTML = '<p>✅ Training completed successfully!</p>';
                }
                loadProjects();
            } else {
                alert('Failed to save model: ' + saveData.error);
            }
            
        } catch (error) {
            console.error('Training error:', error);
            alert('Training failed: ' + error.message);
        } finally {
            trainBtn.disabled = false;
        }
    });
}

// Start recognition - FIXED: Added null check
const startRecognitionBtn = document.getElementById('start-recognition-btn');
if (startRecognitionBtn) {
    startRecognitionBtn.addEventListener('click', () => {
        window.location.href = 'recognize.html';
    });
}

// Download attendance - FIXED: Added null check
const downloadAttendanceBtn = document.getElementById('download-attendance-btn');
if (downloadAttendanceBtn) {
    downloadAttendanceBtn.addEventListener('click', async () => {
        try {
            const response = await fetch(`${API_BASE_URL}/attendance/download`, {  // FIXED: Removed duplicate /api
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
}

// Activate project
async function activateProject(projectId) {
    try {
        const response = await fetch(`${API_BASE_URL}/auth/projects/${projectId}/activate`, {  // FIXED: Removed duplicate /api
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
        const response = await fetch(`${API_BASE_URL}/auth/projects/${projectId}`, {  // FIXED: Removed duplicate /api
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

// Logout - FIXED: Added null check
const logoutBtn = document.getElementById('logout-btn');
if (logoutBtn) {
    logoutBtn.addEventListener('click', async () => {
        await fetch(`${API_BASE_URL}/auth/logout`, {  // FIXED: Removed duplicate /api
            method: 'POST',
            credentials: 'include'
        });
        window.location.href = 'index.html';
    });
}

// Initialize on load
window.addEventListener('load', () => {
    loadProjects();
});
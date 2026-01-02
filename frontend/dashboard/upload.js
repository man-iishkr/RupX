// Dataset Upload Logic
// const API_BASE = "http://127.0.0.1:5000/api"; // Added missing definition

// Helper: Alert Function
function showAlert(message, type = 'info') {
    alert(`${type.toUpperCase()}: ${message}`);
}

const uploadZone = document.getElementById('upload-zone');
const fileInput = document.getElementById('file-input');
const progressContainer = document.getElementById('upload-progress');
const progressFill = document.getElementById('progress-fill');
const progressText = document.getElementById('progress-text');
const validationResults = document.getElementById('validation-results');

// Drag and drop events
uploadZone.addEventListener('dragover', (e) => {
    e.preventDefault();
    uploadZone.classList.add('dragover');
});

uploadZone.addEventListener('dragleave', () => {
    uploadZone.classList.remove('dragover');
});

uploadZone.addEventListener('drop', (e) => {
    e.preventDefault();
    uploadZone.classList.remove('dragover');
    
    const files = e.dataTransfer.files;
    if (files.length > 0) {
        handleFile(files[0]);
    }
});

// File input change
fileInput.addEventListener('change', (e) => {
    if (e.target.files.length > 0) {
        handleFile(e.target.files[0]);
    }
});

// Handle file upload
async function handleFile(file) {
    // Validate file type - MUST BE A ZIP
    if (!file.name.endsWith('.zip')) {
        showAlert('Please select a ZIP file. Folders must be zipped before uploading.', 'error');
        return;
    }
    
    // Show progress
    progressContainer.style.display = 'block';
    validationResults.style.display = 'none';
    
    const formData = new FormData();
    formData.append('file', file);
    
    try {
        const response = await fetch(`${API_BASE}/dataset/upload`, {
            method: 'POST',
            credentials: 'include',
            body: formData
        });
        
        const data = await response.json();
        
        if (response.ok) {
            showAlert('Dataset uploaded successfully!', 'success');
            displayValidationResults(data.stats);
            progressContainer.style.display = 'none';
        } else {
            showAlert(data.error || 'Upload failed', 'error');
            progressContainer.style.display = 'none';
            if (data.details) {
                displayValidationError(data.details);
            }
        }
    } catch (error) {
        console.error('Upload error:', error);
        showAlert('Network error during upload', 'error');
        progressContainer.style.display = 'none';
    }
}

// Display validation results
function displayValidationResults(stats) {
    validationResults.style.display = 'block';
    validationResults.innerHTML = `
        <div class="alert alert-success">
            <span>✓</span>
            <div>
                <strong>Dataset Validated Successfully!</strong>
                <div style="margin-top: 0.5rem; font-size: 0.875rem;">
                    ${stats.total_persons} persons detected with ${stats.total_images} images total
                    ${stats.invalid_persons > 0 ? `<br><span style="color: var(--warning);">⚠ ${stats.invalid_persons} persons skipped (less than 10 images)</span>` : ''}
                </div>
            </div>
        </div>
        <div style="margin-top: 1rem;">
            <strong>Next Step:</strong> Go to <a href="train.html" style="color: var(--primary);">Train Model</a> to start training your face recognition model.
        </div>
    `;
}

// Display validation error
function displayValidationError(details) {
    validationResults.style.display = 'block';
    
    if (details.invalid_persons) {
        validationResults.innerHTML = `
            <div class="alert alert-error">
                <span>✗</span>
                <div>
                    <strong>Validation Failed</strong>
                    <div style="margin-top: 0.5rem; font-size: 0.875rem;">
                        The following persons have insufficient images (minimum 10 required):
                    </div>
                </div>
            </div>
            <div style="margin-top: 1rem; background: var(--bg-card); border: 1px solid var(--border); border-radius: 8px; padding: 1rem;">
                ${details.invalid_persons.map(p => `
                    <div style="display: flex; justify-content: space-between; padding: 0.5rem; border-bottom: 1px solid var(--border);">
                        <span>${p.name}</span>
                        <span style="color: var(--error);">${p.images} / 10 images</span>
                    </div>
                `).join('')}
            </div>
        `;
    }
}

// Check dataset status on load
window.addEventListener('DOMContentLoaded', async () => {
    try {
        const response = await fetch(`${API_BASE}/dataset/status`, {
            credentials: 'include'
        });
        
        const data = await response.json();
        
        if (data.uploaded && data.stats) {
            displayValidationResults(data.stats);
        }
    } catch (error) {
        console.error('Failed to check dataset status:', error);
    }
});
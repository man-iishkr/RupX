// train.js - Updated for client-side ML training
// REPLACE YOUR CURRENT train.js WITH THIS FILE

let mlClient = null;
let trainingInProgress = false;

document.addEventListener('DOMContentLoaded', async () => {
    await checkDatasetStatus();
    
    // Add train button listener
    const trainBtn = document.getElementById('train-btn');
    if (trainBtn) {
        trainBtn.addEventListener('click', startTraining);
    }
});

async function checkDatasetStatus() {
    try {
        const response = await fetch(`${API_BASE_URL}/api/train/status`, {
            credentials: 'include'
        });
        
        const data = await response.json();
        
        if (!data.dataset_uploaded) {
            showAlert('Please upload a dataset first', 'warning');
            // Disable train button if it exists
            const trainBtn = document.getElementById('train-btn');
            if (trainBtn) trainBtn.disabled = true;
        }
    } catch (error) {
        console.error('Failed to check dataset status:', error);
    }
}

async function startTraining() {
    if (trainingInProgress) {
        showAlert('Training already in progress', 'info');
        return;
    }
    
    try {
        trainingInProgress = true;
        const trainBtn = document.getElementById('train-btn');
        if (trainBtn) trainBtn.disabled = true;
        
        updateTrainingStatus('Initializing...', 0);
        
        // Initialize ML Client
        if (!mlClient) {
            updateTrainingStatus('Loading TensorFlow.js models...', 10);
            
            mlClient = new MLClient();
            const result = await mlClient.initialize((progress) => {
                updateTrainingStatus(progress.message, 10 + (progress.progress * 0.2));
            });
            
            if (!result.success) {
                throw new Error(`Failed to load ML models: ${result.error}`);
            }
        }
        
        // Get dataset from backend
        updateTrainingStatus('Fetching dataset...', 30);
        
        const response = await fetch(`${API_BASE_URL}/api/train/start`, {
            method: 'POST',
            credentials: 'include'
        });
        
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.error || 'Failed to start training');
        }
        
        // Train in browser
        updateTrainingStatus('Training in browser...', 40);
        
        const embeddings = await mlClient.trainFromDataset(data.dataset, (progress) => {
            const overallProgress = 40 + (progress.progress * 0.5);
            updateTrainingStatus(progress.message, overallProgress);
            
            if (progress.person) {
                updatePersonProgress(progress.person);
            }
        });
        
        // Send embeddings to backend
        updateTrainingStatus('Saving model...', 90);
        
        const saveResponse = await fetch(`${API_BASE_URL}/api/train/save`, {
            method: 'POST',
            credentials: 'include',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                embeddings: embeddings,
                metadata: {
                    model: 'mobilenet_tfjs',
                    total_images_processed: data.dataset.total_images,
                    trained_at: new Date().toISOString()
                }
            })
        });
        
        const saveData = await saveResponse.json();
        
        if (!saveData.success) {
            throw new Error(saveData.error || 'Failed to save model');
        }
        
        // Training complete
        updateTrainingStatus('Training completed successfully! ✅', 100);
        showAlert(`Training complete! Trained ${embeddings.length} persons.`, 'success');
        
        // Enable test button or redirect
        setTimeout(() => {
            window.location.href = '/dashboard/test.html';
        }, 2000);
        
    } catch (error) {
        console.error('Training error:', error);
        updateTrainingStatus(`Training failed: ${error.message}`, 0, true);
        showAlert(`Training failed: ${error.message}`, 'error');
    } finally {
        trainingInProgress = false;
        const trainBtn = document.getElementById('train-btn');
        if (trainBtn) trainBtn.disabled = false;
    }
}

function updateTrainingStatus(message, progress, isError = false) {
    // Update progress bar if it exists
    const progressBar = document.getElementById('training-progress-bar');
    if (progressBar) {
        progressBar.style.width = `${progress}%`;
        if (isError) {
            progressBar.style.background = 'var(--danger-color, #f44336)';
        } else {
            progressBar.style.background = 'var(--success-color, #4CAF50)';
        }
    }
    
    // Update status message
    const statusElement = document.getElementById('training-status');
    if (statusElement) {
        statusElement.textContent = message;
        if (isError) {
            statusElement.style.color = 'var(--danger-color, #f44336)';
        }
    }
    
    console.log(`Training: ${message} (${Math.round(progress)}%)`);
}

function updatePersonProgress(personName) {
    // Update person-specific progress if UI exists
    const personList = document.getElementById('training-persons-list');
    if (personList) {
        const item = document.createElement('div');
        item.className = 'training-person-item';
        item.innerHTML = `✅ ${personName}`;
        personList.appendChild(item);
    }
}

function showAlert(message, type = 'info') {
    // Use your existing alert system
    console.log(`[${type.toUpperCase()}] ${message}`);
    alert(message);
}
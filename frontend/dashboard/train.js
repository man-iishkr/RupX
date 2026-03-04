// train.js - Updated for client-side ML training
// RETAINS ALL ORIGINAL FUNCTIONS AND LOGIC

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
    const statusCard = document.getElementById('model-status-card');
    try {
        const response = await fetch(`${API_BASE_URL}/train/status`, {
            credentials: 'include'
        });

        const data = await response.json();

        const datasetIcon = data.dataset_uploaded ? '🟠' : '❌';
        const modelIcon = data.model_trained ? '✅' : '⏳';
        const modelLabel = data.model_trained ? 'Trained' : 'Needs Training';
        let imageCount = data.total_images || 0;
        let imageCountNote = '';

        if (data.model_trained) {
            // After training, images are deleted. Show identities instead.
            const identities = data.latest_training?.num_identities;
            imageCountNote = identities
                ? `${identities} identities trained (images removed)`
                : 'Training images removed (model saved)';
        } else {
            imageCountNote = `${imageCount} images found in project`;
        }

        if (statusCard) {
            statusCard.innerHTML = `
                <div class="stat-card">
                    <div class="stat-label">Dataset Status</div>
                    <div class="stat-value">${datasetIcon} ${data.dataset_uploaded ? 'Uploaded' : 'Missing'}</div>
                    <div class="stat-sublabel">${imageCountNote}</div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">Model Status</div>
                    <div class="stat-value">${modelIcon} ${modelLabel}</div>
                    <div class="stat-sublabel">Current Version: 1.0.0</div>
                </div>
            `;
        }

        const trainBtn = document.getElementById('train-btn');
        const retrainNote = document.getElementById('retrain-note');

        if (data.model_trained) {
            // Model is already trained — hide train button, show retrain guidance
            if (trainBtn) trainBtn.style.display = 'none';
            if (retrainNote) {
                retrainNote.style.display = 'block';
                retrainNote.innerHTML = `
                    <div class="alert-info" style="margin-top: 1rem; padding: 1rem; background: rgba(255,120,73,0.1); border-radius: 8px; border: 1px solid #ff7849;">
                        ✅ <strong>Model is trained and ready for recognition.</strong><br>
                        To retrain, upload a new dataset on the <a href="/dashboard/upload.html">Upload page</a>.
                    </div>
                `;
            }
        } else if (!data.dataset_uploaded) {
            // Nothing uploaded yet
            if (trainBtn) { trainBtn.style.display = 'none'; trainBtn.disabled = true; }
            showAlert('Please upload a dataset first', 'warning');
        } else {
            // Dataset uploaded, model not trained — show train button
            if (trainBtn) {
                trainBtn.style.display = 'block';
                trainBtn.disabled = false;
            }
        }
    } catch (error) {
        console.error('Failed to check dataset status:', error);
        if (statusCard) statusCard.innerHTML = '<p style="color: red;">Error connecting to server.</p>';
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

        // Show progress UI
        const progressDiv = document.getElementById('training-progress');
        if (progressDiv) progressDiv.style.display = 'block';

        updateTrainingStatus('Initializing...', 0);

        // Initialize ML Client using the global instance from dashboard.js
        if (!window.mlClient) {
            updateTrainingStatus('Loading TensorFlow.js models...', 10);

            window.mlClient = new MLClient();
            const result = await window.mlClient.initialize((progress) => {
                updateTrainingStatus(progress.message, 10 + (progress.progress * 0.2));
            });

            if (!result.success) {
                throw new Error(`Failed to load ML models: ${result.error}`);
            }
        }

        // Get dataset from backend
        updateTrainingStatus('Fetching dataset...', 30);

        // FIXED: Removed extra /api/ from path
        const response = await fetch(`${API_BASE_URL}/train/start`, {
            method: 'POST',
            credentials: 'include'
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.error || 'Failed to start training');
        }

        // Train in browser
        updateTrainingStatus('Training in browser...', 40);

        const embeddings = await window.mlClient.trainFromDataset(data.dataset, (progress) => {
            const overallProgress = 40 + (progress.progress * 0.5);
            updateTrainingStatus(progress.message, overallProgress);

            if (progress.person) {
                updatePersonProgress(progress.person);
            }
        });

        // Send embeddings to backend
        // Inside startTraining function in train.js
        updateTrainingStatus('Saving model...', 90);

        // Inside startTraining in train.js
        const saveResponse = await fetch(`${API_BASE_URL}/train/save`, {
            method: 'POST',
            credentials: 'include',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                // Ensure this is a list of {name, embedding} objects
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
    const progressBar = document.getElementById('progress-fill');
    if (progressBar) {
        progressBar.style.width = `${progress}%`;
        progressBar.style.background = isError ? '#f44336' : '#ff7849';
    }

    const statusElement = document.getElementById('progress-title');
    if (statusElement) {
        statusElement.textContent = message;
        if (isError) statusElement.style.color = '#f44336';
    }

    const progressText = document.getElementById('progress-text');
    if (progressText) {
        progressText.textContent = `${Math.round(progress)}%`;
    }
}

function updatePersonProgress(personName) {
    const personList = document.getElementById('training-stats');
    if (personList) {
        personList.style.display = 'grid';
        const item = document.createElement('div');
        item.className = 'stat-card';
        item.style.padding = '10px';
        item.innerHTML = `✅ ${personName} processed`;
        personList.appendChild(item);
    }
}

function showAlert(message, type = 'info') {
    console.log(`[${type.toUpperCase()}] ${message}`);
    alert(message);
}
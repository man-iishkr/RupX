// test.js - Updated for client-side ML processing
// REPLACE YOUR CURRENT test.js WITH THIS FILE

let socket = null;
let webcamStream = null;
let recognitionActive = false;
// let mlClient = null;
let markedToday = [];

// Initialize when page loads
document.addEventListener('DOMContentLoaded', async () => {
    await checkModelStatus();
});

async function checkModelStatus() {
    try {
        const response = await fetch(`${API_BASE_URL}/train/status`, {
            credentials: 'include'
        });

        const data = await response.json();

        if (!data.model_trained) {
            document.getElementById('not-trained-message').style.display = 'block';
            document.getElementById('recognition-container').style.display = 'none';
        } else {
            document.getElementById('not-trained-message').style.display = 'none';
            document.getElementById('recognition-container').style.display = 'block';

            // Initialize ML Client
            await initializeMLClient();
        }
    } catch (error) {
        console.error('Failed to check model status:', error);
        showAlert('Failed to check model status', 'error');
    }
}

async function initializeMLClient() {
    try {
        console.log('Loading TensorFlow.js models...');

        mlClient = new MLClient();
        const result = await mlClient.initialize((progress) => {
            console.log(`Loading models... ${progress.progress}% - ${progress.message}`);
        });

        if (!result.success) {
            showAlert(`Failed to load ML models: ${result.error}`, 'error');
            return false;
        }

        console.log('ML models loaded successfully');
        return true;

    } catch (error) {
        console.error('Failed to initialize ML client:', error);
        showAlert('Failed to load face recognition models', 'error');
        return false;
    }
}

async function startRecognition() {
    try {
        // Make sure ML Client is ready
        if (!mlClient || !mlClient.isReady) {
            showAlert('Loading ML models, please wait...', 'info');
            const success = await initializeMLClient();
            if (!success) return;
        }

        // Start webcam
        webcamStream = await navigator.mediaDevices.getUserMedia({
            video: { width: 640, height: 480, facingMode: 'user' }
        });

        const video = document.getElementById('webcam');
        video.srcObject = webcamStream;

        // Wait for video to be ready
        await new Promise(resolve => {
            video.onloadedmetadata = resolve;
        });

        // Connect to API session
        await connectSession();

        // Start recognition loop
        recognitionActive = true;
        document.getElementById('start-btn').style.display = 'none';
        document.getElementById('stop-btn').style.display = 'inline-block';

        processFrames();

    } catch (error) {
        console.error('Failed to start recognition:', error);
        if (error.name === 'NotAllowedError') {
            showAlert('Camera access denied. Please allow camera access and try again.', 'error');
        } else {
            showAlert('Failed to start recognition: ' + error.message, 'error');
        }
    }
}

async function connectSession() {
    try {
        const response = await fetch(`${API_BASE_URL}/recognize/start`, {
            method: 'POST',
            credentials: 'include',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                user_id: window.currentUser?.id,
                project_id: window.activeProject?.id
            })
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.error || 'Failed to start session');
        }

        console.log('✅ Recognition session started:', data);
        return true;
    } catch (error) {
        console.error('❌ Recognition error:', error);
        showAlert(`Recognition error: ${error.message}`, 'error');
        throw error;
    }
}

async function processFrames() {
    if (!recognitionActive) return;

    try {
        const video = document.getElementById('webcam');
        const canvas = document.getElementById('overlay');
        const ctx = canvas.getContext('2d');

        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;
        ctx.clearRect(0, 0, canvas.width, canvas.height);

        // Single pass: detect all faces + get descriptors
        const detections = await faceapi
            .detectAllFaces(video, new faceapi.SsdMobilenetv1Options({ minConfidence: mlClient.minConfidence }))
            .withFaceLandmarks()
            .withFaceDescriptors();

        ctx.lineWidth = 3;
        ctx.font = 'bold 15px Arial';

        for (const det of detections) {
            const box = det.detection.box;
            const embedding = Array.from(det.descriptor);

            let label = '...';
            let color = '#ffcc00';

            try {
                const response = await fetch(`${API_BASE_URL}/recognize/frame`, {
                    method: 'POST',
                    credentials: 'include',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ embedding })
                });
                const data = await response.json();
                if (data.success && data.persons && data.persons.length > 0) {
                    const person = data.persons[0];
                    if (person.name !== 'Unknown') {
                        label = `${person.name} ${Math.round(person.confidence * 100)}%`;
                        color = '#00ff88';
                        if (person.newly_marked) {
                            addToMarkedList(person.name, person.confidence);
                        }
                    } else {
                        label = 'Unknown';
                        color = '#ff4444';
                    }
                }
            } catch (apiErr) {
                console.error('Frame API error:', apiErr);
            }

            // Draw colored box
            ctx.strokeStyle = color;
            ctx.strokeRect(box.x, box.y, box.width, box.height);

            // Label background
            const tw = ctx.measureText(label).width;
            ctx.fillStyle = 'rgba(0,0,0,0.65)';
            ctx.fillRect(box.x, box.y - 26, tw + 12, 22);
            ctx.fillStyle = color;
            ctx.fillText(label, box.x + 6, box.y - 9);
        }

    } catch (error) {
        console.error('Frame processing error:', error);
    }

    setTimeout(processFrames, 250); // ~4 FPS
}

function stopRecognition() {
    recognitionActive = false;

    // Stop webcam
    if (webcamStream) {
        webcamStream.getTracks().forEach(track => track.stop());
        const video = document.getElementById('webcam');
        video.srcObject = null;
    }

    // Disconnect API session
    fetch(`${API_BASE_URL}/recognize/stop`, {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            user_id: window.currentUser?.id,
            project_id: window.activeProject?.id
        })
    }).catch(console.error);

    // Clear canvas
    const canvas = document.getElementById('overlay');
    const ctx = canvas.getContext('2d');
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // Update buttons
    document.getElementById('start-btn').style.display = 'inline-block';
    document.getElementById('stop-btn').style.display = 'none';
}

function addToMarkedList(name, confidence) {
    if (markedToday.includes(name)) return;

    markedToday.push(name);

    const markedList = document.getElementById('marked-list');

    // Remove "no one marked" message if it exists
    if (markedList.querySelector('p')) {
        markedList.innerHTML = '';
    }

    const item = document.createElement('div');
    item.className = 'marked-item';
    item.innerHTML = `
        <div class="marked-info">
            <strong>${name}</strong>
            <span class="confidence">${Math.round(confidence * 100)}% match</span>
        </div>
        <div class="marked-time">${new Date().toLocaleTimeString()}</div>
    `;

    markedList.prepend(item);

    // Add animation
    item.style.animation = 'slideIn 0.3s ease-out';
}

// Cleanup on page unload
window.addEventListener('beforeunload', () => {
    if (recognitionActive) {
        stopRecognition();
    }
    if (mlClient) {
        mlClient.cleanup();
    }
});

function showAlert(message, type = 'info') {
    // Use your existing alert system
    console.log(`[${type.toUpperCase()}] ${message}`);
    alert(message);
}
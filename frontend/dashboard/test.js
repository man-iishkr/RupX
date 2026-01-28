// test.js - Updated for client-side ML processing
// REPLACE YOUR CURRENT test.js WITH THIS FILE

let socket = null;
let webcamStream = null;
let recognitionActive = false;
let mlClient = null;
let markedToday = [];

// Initialize when page loads
document.addEventListener('DOMContentLoaded', async () => {
    await checkModelStatus();
});

async function checkModelStatus() {
    try {
        const response = await fetch(`${API_BASE_URL}/api/train/status`, {
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
        
        // Connect to WebSocket
        await connectWebSocket();
        
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

async function connectWebSocket() {
    return new Promise((resolve, reject) => {
        socket = io(API_BASE_URL, {
            withCredentials: true,
            transports: ['websocket']
        });
        
        socket.on('connect', () => {
            console.log('✅ WebSocket connected');
            
            // Start recognition session on backend
            socket.emit('start_recognition', {
                user_id: window.currentUser?.id,
                project_id: window.activeProject?.id
            });
        });
        
        socket.on('recognition_started', (data) => {
            console.log('🎯 Recognition session started:', data);
            resolve();
        });
        
        socket.on('face_recognized', (data) => {
            console.log('✅ Face recognized:', data);
            data.persons.forEach(person => {
                if (person.newly_marked) {
                    addToMarkedList(person.name, person.confidence);
                }
            });
        });
        
        socket.on('recognition_error', (data) => {
            console.error('❌ Recognition error:', data);
            showAlert(`Recognition error: ${data.error}`, 'error');
            reject(new Error(data.error));
        });
        
        socket.on('connect_error', (error) => {
            console.error('WebSocket connection error:', error);
            reject(error);
        });
    });
}

async function processFrames() {
    if (!recognitionActive) return;
    
    try {
        const video = document.getElementById('webcam');
        const canvas = document.getElementById('overlay');
        const ctx = canvas.getContext('2d');
        
        // Set canvas size to match video
        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;
        
        // Clear previous drawings
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        
        // Detect faces using TensorFlow.js
        const faces = await mlClient.detectFaces(video);
        
        // Draw bounding boxes
        ctx.strokeStyle = '#00ff00';
        ctx.lineWidth = 3;
        ctx.font = '16px Arial';
        ctx.fillStyle = '#00ff00';
        
        for (const face of faces) {
            // Draw rectangle
            ctx.strokeRect(face.box.x, face.box.y, face.box.width, face.box.height);
            
            // Draw confidence
            ctx.fillText(
                `${Math.round(face.confidence * 100)}%`,
                face.box.x,
                face.box.y - 5
            );
            
            // Generate embedding and send to backend
            const embedding = await mlClient.generateEmbedding(video, face.box);
            
            socket.emit('recognize_embedding', {
                embedding: embedding,
                user_id: window.currentUser?.id,
                project_id: window.activeProject?.id,
                timestamp: new Date().toISOString()
            });
        }
        
    } catch (error) {
        console.error('Frame processing error:', error);
    }
    
    // Continue processing frames (10 FPS)
    setTimeout(processFrames, 100);
}

function stopRecognition() {
    recognitionActive = false;
    
    // Stop webcam
    if (webcamStream) {
        webcamStream.getTracks().forEach(track => track.stop());
        const video = document.getElementById('webcam');
        video.srcObject = null;
    }
    
    // Disconnect WebSocket
    if (socket) {
        socket.emit('stop_recognition', {
            user_id: window.currentUser?.id,
            project_id: window.activeProject?.id
        });
        socket.disconnect();
        socket = null;
    }
    
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
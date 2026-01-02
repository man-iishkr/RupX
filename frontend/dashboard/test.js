// Face Recognition Testing with WebSocket
// const API_BASE = "http://127.0.0.1:5000/api";

let socket = null;
let webcamStream = null;
let isRecognizing = false;
let userId = null;
let projectId = null;
let frameInterval = null;

// Check if model is trained
window.addEventListener('DOMContentLoaded', async () => {
    await checkModelTrained();
});

// Check if model is trained
async function checkModelTrained() {
    try {
        const response = await fetch(`${API_BASE}/train/status`, {
            credentials: 'include'
        });
        
        const data = await response.json();
        
        if (data.model_trained) {
            document.getElementById('recognition-container').style.display = 'block';
            document.getElementById('not-trained-message').style.display = 'none';
            await initializeWebcam();
            await loadMarkedToday();
        } else {
            document.getElementById('recognition-container').style.display = 'none';
            document.getElementById('not-trained-message').style.display = 'block';
        }
    } catch (error) {
        console.error('Failed to check model status:', error);
        showAlert('Failed to load status', 'error');
    }
}

// Initialize webcam
async function initializeWebcam() {
    try {
        const video = document.getElementById('webcam');
        const stream = await navigator.mediaDevices.getUserMedia({
            video: {
                width: { ideal: 640 },
                height: { ideal: 480 }
            }
        });
        
        video.srcObject = stream;
        webcamStream = stream;
    } catch (error) {
        console.error('Webcam error:', error);
        showAlert('Failed to access webcam. Please check permissions.', 'error');
    }
}

// Start recognition
async function startRecognition() {
    if (isRecognizing) return;
    
    try {
        // Start recognition session on backend
        const response = await fetch(`${API_BASE}/recognize/start`, {
            method: 'POST',
            credentials: 'include'
        });
        
        const data = await response.json();
        
        if (!response.ok) {
            showAlert(data.error || 'Failed to start recognition', 'error');
            return;
        }
        
        isRecognizing = true;
        
        // Update UI
        document.getElementById('start-btn').style.display = 'none';
        document.getElementById('stop-btn').style.display = 'inline-block';
        
        // Initialize WebSocket
        initializeWebSocket();
        
        // Start sending frames
        startFrameCapture();
        
        showAlert('Recognition started', 'success');
    } catch (error) {
        console.error('Start recognition error:', error);
        showAlert('Network error', 'error');
    }
}

// Stop recognition
async function stopRecognition() {
    if (!isRecognizing) return;
    
    try {
        // Stop frame capture
        if (frameInterval) {
            clearInterval(frameInterval);
            frameInterval = null;
        }
        
        // Disconnect WebSocket
        if (socket) {
            socket.disconnect();
            socket = null;
        }
        
        // Stop recognition session on backend
        await fetch(`${API_BASE}/recognize/stop`, {
            method: 'POST',
            credentials: 'include'
        });
        
        isRecognizing = false;
        
        // Update UI
        document.getElementById('start-btn').style.display = 'inline-block';
        document.getElementById('stop-btn').style.display = 'none';
        
        showAlert('Recognition stopped', 'success');
    } catch (error) {
        console.error('Stop recognition error:', error);
    }
}

// Initialize WebSocket connection
function initializeWebSocket() {
    socket = io('http://127.0.0.1:5000');
    
    socket.on('connect', () => {
        console.log('WebSocket connected');
        
        // Get user/project info from session
        fetch(`${API_BASE}/auth/status`, { credentials: 'include' })
            .then(res => res.json())
            .then(data => {
                if (data.authenticated) {
                    userId = data.user.id;
                    
                    // Get active project
                    return fetch(`${API_BASE}/auth/projects`, { credentials: 'include' });
                }
            })
            .then(res => res.json())
            .then(data => {
                const activeProject = data.projects.find(p => p.is_active);
                if (activeProject) {
                    projectId = activeProject.id;
                    
                    // Start stream
                    socket.emit('start_stream', {
                        user_id: userId,
                        project_id: projectId
                    });
                }
            });
    });
    
    socket.on('stream_started', () => {
        console.log('Stream started');
    });
    
    socket.on('attendance_marked', (data) => {
        console.log('Attendance marked:', data);
        addMarkedPerson(data.name, data.time);
        showAlert(`✓ ${data.name} marked at ${data.time}`, 'success');
    });
    
    socket.on('error', (data) => {
        console.error('WebSocket error:', data);
        showAlert(data.message, 'error');
    });
    
    socket.on('disconnect', () => {
        console.log('WebSocket disconnected');
    });
}

// Start capturing and sending frames
function startFrameCapture() {
    const video = document.getElementById('webcam');
    const canvas = document.createElement('canvas');
    const ctx = canvas.getContext('2d');
    
    // Send frame every 300ms (3-4 fps)
    frameInterval = setInterval(() => {
        if (!video.videoWidth || !video.videoHeight) return;
        
        // Set canvas size to match video
        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;
        
        // Draw current frame
        ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
        
        // Convert to base64
        const frameData = canvas.toDataURL('image/jpeg', 0.8);
        
        // Send via WebSocket
        if (socket && socket.connected) {
            socket.emit('video_frame', {
                user_id: userId,
                project_id: projectId,
                frame: frameData
            });
        }
    }, 300);
}

// Load today's marked attendance
async function loadMarkedToday() {
    try {
        const response = await fetch(`${API_BASE}/attendance/today`, {
            credentials: 'include'
        });
        
        const data = await response.json();
        
        if (data.marked && data.marked.length > 0) {
            const markedList = document.getElementById('marked-list');
            markedList.innerHTML = data.marked.map(item => `
                <div class="attendance-item">
                    <span class="attendance-name">${item.name}</span>
                    <span class="attendance-time">${item.time}</span>
                </div>
            `).join('');
        }
    } catch (error) {
        console.error('Failed to load marked attendance:', error);
    }
}

// Add newly marked person to list
function addMarkedPerson(name, time) {
    const markedList = document.getElementById('marked-list');
    
    // Remove "no one marked" message if exists
    if (markedList.querySelector('p')) {
        markedList.innerHTML = '';
    }
    
    // Add new item at top
    const item = document.createElement('div');
    item.className = 'attendance-item';
    item.innerHTML = `
        <span class="attendance-name">${name}</span>
        <span class="attendance-time">${time}</span>
    `;
    
    markedList.insertBefore(item, markedList.firstChild);
}

// Cleanup on page unload
window.addEventListener('beforeunload', () => {
    if (isRecognizing) {
        stopRecognition();
    }
    
    if (webcamStream) {
        webcamStream.getTracks().forEach(track => track.stop());
    }
});
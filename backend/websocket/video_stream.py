"""
WebSocket video streaming with face recognition
FIXED: Embeddings loading issue
"""
import cv2
import numpy as np
import base64
import threading
import time
from datetime import datetime
import pandas as pd
from queue import Queue, Empty
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ml.face_embedding import get_model
from ml.recognition_core import FaceTracker
from flask import request

# Global state
socketio = None
recognition_sessions = {}
session_lock = threading.Lock()

def init_socketio(sio):
    """Initialize SocketIO instance"""
    global socketio
    socketio = sio
    
    @socketio.on('connect')
    def handle_connect():
        print(f"Client connected: {request.sid}")
    
    @socketio.on('disconnect')
    def handle_disconnect():
        print(f"Client disconnected: {request.sid}")
    
    @socketio.on('start_stream')
    def handle_start_stream(data):
        """Start video streaming"""
        user_id = data.get('user_id')
        project_id = data.get('project_id')
        
        if not user_id or not project_id:
            socketio.emit('error', {'message': 'Invalid session'}, room=request.sid)
            return
        
        key = f"{user_id}_{project_id}"
        
        with session_lock:
            if key in recognition_sessions:
                session = recognition_sessions[key]
                session['clients'].add(request.sid)
                socketio.emit('stream_started', {}, room=request.sid)
            else:
                socketio.emit('error', {'message': 'Recognition not started'}, room=request.sid)
    
    @socketio.on('stop_stream')
    def handle_stop_stream(data):
        """Stop video streaming"""
        user_id = data.get('user_id')
        project_id = data.get('project_id')
        
        if not user_id or not project_id:
            return
        
        key = f"{user_id}_{project_id}"
        
        with session_lock:
            if key in recognition_sessions:
                session = recognition_sessions[key]
                if request.sid in session['clients']:
                    session['clients'].remove(request.sid)
    
    @socketio.on('video_frame')
    def handle_video_frame(data):
        """Process incoming video frame"""
        user_id = data.get('user_id')
        project_id = data.get('project_id')
        frame_data = data.get('frame')
        
        if not all([user_id, project_id, frame_data]):
            return
        
        key = f"{user_id}_{project_id}"
        
        with session_lock:
            if key not in recognition_sessions:
                return
            
            session = recognition_sessions[key]
            
            if not session['running']:
                return
        
        try:
            # Decode frame
            frame_bytes = base64.b64decode(frame_data.split(',')[1])
            nparr = np.frombuffer(frame_bytes, np.uint8)
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            if frame is None:
                return
            
            # Add to processing queue
            if not session['frame_queue'].full():
                session['frame_queue'].put({
                    'frame': frame,
                    'timestamp': time.time()
                })
        
        except Exception as e:
            print(f"Error processing frame: {e}")

def start_recognition_session(user_id, project_id, embeddings_path, attendance_path, attendance_mode):
    """Start recognition session"""
    global recognition_sessions
    
    key = f"{user_id}_{project_id}"
    
    with session_lock:
        if key in recognition_sessions and recognition_sessions[key]['running']:
            return False
        
        # Load embeddings - FIX: Handle new format with metadata
        try:
            data = np.load(embeddings_path, allow_pickle=True).item()
            
            # Check if it's the new format with 'embeddings' key
            if isinstance(data, dict) and 'embeddings' in data:
                embeddings = data['embeddings']
            else:
                # Old format - direct embeddings dict
                embeddings = data
            
            print(f"Loaded {len(embeddings)} embeddings")
            
        except Exception as e:
            print(f"Error loading embeddings: {e}")
            return False
        
        # Load attendance
        attendance_df = pd.read_excel(attendance_path, engine='openpyxl')
        
        # Get already marked names
        marked_today = set()
        today = datetime.now().strftime('%Y-%m-%d')
        if today in attendance_df.columns:
            for idx, row in attendance_df.iterrows():
                if not pd.isna(row[today]) and row[today] != "":
                    marked_today.add(row["NAME"])
        
        # Create session
        session = {
            'user_id': user_id,
            'project_id': project_id,
            'embeddings': embeddings,
            'attendance_df': attendance_df,
            'attendance_path': attendance_path,
            'attendance_mode': attendance_mode,
            'marked_today': marked_today,
            'running': True,
            'clients': set(),
            'frame_queue': Queue(maxsize=2),
            'tracker': FaceTracker()
        }
        
        recognition_sessions[key] = session
        
        # Start processing thread
        thread = threading.Thread(
            target=recognition_worker,
            args=(key,),
            daemon=True
        )
        thread.start()
        
        return True

def stop_recognition_session(user_id, project_id):
    """Stop recognition session"""
    global recognition_sessions
    
    key = f"{user_id}_{project_id}"
    
    with session_lock:
        if key in recognition_sessions:
            recognition_sessions[key]['running'] = False
            # Will be cleaned up by worker thread

def get_recognition_status(user_id, project_id):
    """Get recognition session status"""
    key = f"{user_id}_{project_id}"
    
    with session_lock:
        if key in recognition_sessions and recognition_sessions[key]['running']:
            session = recognition_sessions[key]
            return {
                'running': True,
                'marked_today': list(session['marked_today']),
                'tracked_faces': session['tracker'].get_tracked_count()
            }
        else:
            return {
                'running': False,
                'marked_today': [],
                'tracked_faces': 0
            }

def mark_attendance(session, name):
    """Mark attendance for recognized person"""
    today = datetime.now().strftime('%Y-%m-%d')
    current_time = datetime.now().strftime('%H:%M:%S')
    
    df = session['attendance_df']
    
    # Check if already marked
    if name in session['marked_today']:
        return False
    
    # Check if name exists
    if name not in df["NAME"].values:
        return False
    
    # Add column if not exists
    if today not in df.columns:
        df[today] = ""
    
    # Mark attendance
    row_index = df[df["NAME"] == name].index[0]
    
    if pd.isna(df.at[row_index, today]) or df.at[row_index, today] == "":
        df.at[row_index, today] = current_time
        df.to_excel(session['attendance_path'], index=False, engine='openpyxl')
        session['marked_today'].add(name)
        print(f"✅ {name} marked at {current_time}")
        
        # Emit to all clients
        if socketio:
            key = f"{session['user_id']}_{session['project_id']}"
            for client_id in session['clients']:
                socketio.emit('attendance_marked', {
                    'name': name,
                    'time': current_time
                }, room=client_id)
        
        return True
    
    return False

def recognition_worker(session_key):
    """Background thread for face recognition"""
    global recognition_sessions
    
    print(f"Recognition worker started for {session_key}")
    
    # Get model
    model = get_model()
    
    frame_count = 0
    PROCESS_EVERY_N_FRAMES = 3
    
    while True:
        with session_lock:
            if session_key not in recognition_sessions:
                break
            
            session = recognition_sessions[session_key]
            
            if not session['running']:
                # Cleanup
                del recognition_sessions[session_key]
                print(f"Recognition worker stopped for {session_key}")
                break
        
        try:
            # Get frame from queue
            frame_data = session['frame_queue'].get(timeout=0.5)
            frame = frame_data['frame']
            frame_count += 1
            
            # Skip frames for performance
            if frame_count % PROCESS_EVERY_N_FRAMES != 0:
                continue
            
            # Detect faces
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            faces = model.get(frame_rgb)
            
            if faces:
                # Prepare detected faces
                detected_faces = []
                for face in faces:
                    bbox = face.bbox.astype(int)
                    x1, y1, x2, y2 = bbox
                    
                    # Clamp to frame boundaries
                    x1 = max(0, min(x1, frame.shape[1] - 1))
                    y1 = max(0, min(y1, frame.shape[0] - 1))
                    x2 = max(0, min(x2, frame.shape[1]))
                    y2 = max(0, min(y2, frame.shape[0]))
                    
                    bbox_final = (x1, y1, x2, y2)
                    embedding = face.normed_embedding
                    
                    detected_faces.append((bbox_final, embedding))
                
                # Update tracker
                recognized = session['tracker'].update(detected_faces, session['embeddings'])
                
                # Mark attendance
                for face_id, bbox, name, score in recognized:
                    if name != "Unknown" and score > 0.38:
                        mark_attendance(session, name)
            
        except Empty:
            continue
        except Exception as e:
            print(f"Recognition worker error: {e}")
            import traceback
            traceback.print_exc()
            time.sleep(0.1)
    
    print(f"Recognition worker exited for {session_key}")
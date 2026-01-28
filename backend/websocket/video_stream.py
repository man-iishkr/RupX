"""
WebSocket Video Stream Handler
Modified: Receives embeddings from client instead of images
"""

import json
import numpy as np
import os
from datetime import datetime
import pandas as pd

recognition_sessions = {}

def init_socketio(socketio_instance):
    """Initialize WebSocket handlers"""
    
    @socketio_instance.on('connect')
    def handle_connect():
        print(f"✅ Client connected")
        socketio_instance.emit('connection_status', {
            'status': 'connected',
            'message': 'Connected to server'
        })
    
    @socketio_instance.on('disconnect')
    def handle_disconnect():
        print("❌ Client disconnected")
    
    @socketio_instance.on('start_recognition')
    def handle_start_recognition(data):
        """Start recognition session"""
        user_id = data.get('user_id')
        project_id = data.get('project_id')
        
        if not user_id or not project_id:
            socketio_instance.emit('recognition_error', {
                'error': 'Missing user_id or project_id'
            })
            return
        
        session_key = f"{user_id}_{project_id}"
        
        # Load embeddings
        embeddings_file = f'storage/users/{user_id}/projects/{project_id}/models/embeddings.json'
        attendance_file = f'storage/users/{user_id}/projects/{project_id}/attendance/attendance.xlsx'
        
        if not os.path.exists(embeddings_file):
            socketio_instance.emit('recognition_error', {
                'error': 'Model not trained. Please train first.'
            })
            return
        
        if not os.path.exists(attendance_file):
            socketio_instance.emit('recognition_error', {
                'error': 'Attendance file not found'
            })
            return
        
        # Load embeddings from JSON
        with open(embeddings_file, 'r') as f:
            embeddings_data = json.load(f)
        
        recognition_sessions[session_key] = {
            'user_id': user_id,
            'project_id': project_id,
            'embeddings': embeddings_data['embeddings'],
            'attendance_path': attendance_file,
            'marked_today': set(),
            'started_at': datetime.now().isoformat()
        }
        
        socketio_instance.emit('recognition_started', {
            'success': True,
            'num_identities': len(embeddings_data['embeddings']),
            'message': 'Recognition started'
        })
        
        print(f"🎯 Recognition started for user {user_id}, project {project_id}")
    
    @socketio_instance.on('recognize_embedding')
    def handle_recognize_embedding(data):
        """Receive and compare embedding from client"""
        user_id = data.get('user_id')
        project_id = data.get('project_id')
        embedding = data.get('embedding')
        
        if not user_id or not project_id or not embedding:
            socketio_instance.emit('recognition_error', {
                'error': 'Missing required data'
            })
            return
        
        session_key = f"{user_id}_{project_id}"
        
        if session_key not in recognition_sessions:
            socketio_instance.emit('recognition_error', {
                'error': 'Recognition not started'
            })
            return
        
        session_data = recognition_sessions[session_key]
        
        # Convert to numpy
        try:
            detected_embedding = np.array(embedding, dtype=np.float32)
            
            if detected_embedding.shape[0] != 512:
                socketio_instance.emit('recognition_error', {
                    'error': f'Invalid embedding dimension: {detected_embedding.shape[0]}'
                })
                return
            
            # Normalize
            detected_embedding = detected_embedding / np.linalg.norm(detected_embedding)
            
        except Exception as e:
            socketio_instance.emit('recognition_error', {
                'error': f'Failed to process embedding: {str(e)}'
            })
            return
        
        # Compare with stored embeddings
        recognized_persons = []
        
        for stored_person in session_data['embeddings']:
            stored_embedding = np.array(stored_person['embedding'], dtype=np.float32)
            stored_embedding = stored_embedding / np.linalg.norm(stored_embedding)
            
            # Calculate cosine similarity
            similarity = cosine_similarity(detected_embedding, stored_embedding)
            
            if similarity > 0.6:  # Match threshold
                person_name = stored_person['name']
                
                # Check if already marked today
                today = datetime.now().strftime('%Y-%m-%d')
                mark_key = f"{person_name}_{today}"
                
                if mark_key not in session_data['marked_today']:
                    # Mark attendance
                    success = mark_attendance(person_name, session_data['attendance_path'])
                    
                    if success:
                        session_data['marked_today'].add(mark_key)
                        recognized_persons.append({
                            'name': person_name,
                            'confidence': float(similarity),
                            'timestamp': datetime.now().isoformat(),
                            'newly_marked': True
                        })
                else:
                    recognized_persons.append({
                        'name': person_name,
                        'confidence': float(similarity),
                        'timestamp': datetime.now().isoformat(),
                        'newly_marked': False
                    })
        
        # Send results
        if recognized_persons:
            socketio_instance.emit('face_recognized', {
                'persons': recognized_persons
            })
    
    @socketio_instance.on('stop_recognition')
    def handle_stop_recognition(data):
        """Stop recognition session"""
        user_id = data.get('user_id')
        project_id = data.get('project_id')
        
        session_key = f"{user_id}_{project_id}"
        
        if session_key in recognition_sessions:
            marked_count = len(recognition_sessions[session_key]['marked_today'])
            del recognition_sessions[session_key]
            
            socketio_instance.emit('recognition_stopped', {
                'success': True,
                'message': f'Recognition stopped. Marked {marked_count} today.'
            })
            
            print(f"🛑 Recognition stopped")

def cosine_similarity(emb1, emb2):
    """Calculate cosine similarity"""
    dot_product = np.dot(emb1, emb2)
    norm_a = np.linalg.norm(emb1)
    norm_b = np.linalg.norm(emb2)
    
    if norm_a == 0 or norm_b == 0:
        return 0.0
    
    return dot_product / (norm_a * norm_b)

def mark_attendance(person_name, attendance_path):
    """Mark attendance in Excel"""
    try:
        df = pd.read_excel(attendance_path)
        today = datetime.now().strftime('%Y-%m-%d')
        time_now = datetime.now().strftime('%I:%M %p')
        
        # Add date column if needed
        if today not in df.columns:
            df[today] = ''
        
        # Find person row
        person_rows = df[df['NAME'] == person_name].index
        
        if len(person_rows) == 0:
            print(f"⚠️  Person '{person_name}' not found")
            return False
        
        person_row = person_rows[0]
        df.at[person_row, today] = time_now
        
        # Save
        df.to_excel(attendance_path, index=False, engine='openpyxl')
        
        print(f"✅ Marked: {person_name} at {time_now}")
        return True
        
    except Exception as e:
        print(f"❌ Failed to mark attendance: {str(e)}")
        return False
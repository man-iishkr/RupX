"""
WebSocket Video Stream Handler
Modified: Receives embeddings from client, loads trained embeddings from DB
"""

import json
import numpy as np
from datetime import datetime
from utils.db import get_db

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
        """Start recognition session - loads embeddings from DB"""
        user_id = data.get('user_id')
        project_id = data.get('project_id')
        
        if not user_id or not project_id:
            socketio_instance.emit('recognition_error', {
                'error': 'Missing user_id or project_id'
            })
            return
        
        session_key = f"{user_id}_{project_id}"
        
        # Load embeddings from database instead of filesystem
        try:
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute('''
                SELECT embeddings_data, attendance_mode 
                FROM projects 
                WHERE id = ? AND user_id = ? AND model_trained = 1
            ''', (project_id, user_id))
            
            row = cursor.fetchone()
            conn.close()
            
            if not row:
                socketio_instance.emit('recognition_error', {
                    'error': 'Model not trained. Please train first.'
                })
                return
            
            project_data = dict(row)
            embeddings_raw = project_data.get('embeddings_data')
            
            if not embeddings_raw:
                socketio_instance.emit('recognition_error', {
                    'error': 'No embeddings found. Please train the model first.'
                })
                return
            
            embeddings_data = json.loads(embeddings_raw)
            
        except Exception as e:
            print(f"❌ Error loading embeddings from DB: {e}")
            socketio_instance.emit('recognition_error', {
                'error': f'Failed to load embeddings: {str(e)}'
            })
            return
        
        recognition_sessions[session_key] = {
            'user_id': user_id,
            'project_id': project_id,
            'embeddings': embeddings_data['embeddings'],
            'attendance_mode': project_data.get('attendance_mode', 'daily'),
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
                    # Mark attendance in database
                    success = mark_attendance_db(
                        person_name, 
                        session_data['project_id']
                    )
                    
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

def mark_attendance_db(person_name, project_id):
    """Mark attendance in database using attendance_records table"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO attendance_records (project_id, name, marked_at, session_id)
            VALUES (?, ?, ?, ?)
        ''', (project_id, person_name, datetime.now().isoformat(), 
              datetime.now().strftime('%Y-%m-%d')))
        
        conn.commit()
        conn.close()
        
        print(f"✅ Marked: {person_name} at {datetime.now().strftime('%I:%M %p')}")
        return True
        
    except Exception as e:
        print(f"❌ Failed to mark attendance: {str(e)}")
        return False

def get_recognition_status(user_id, project_id):
    """Bridge for recognize.py to check if a session is active"""
    session_key = f"{user_id}_{project_id}"
    if session_key in recognition_sessions:
        return {
            'active': True,
            'started_at': recognition_sessions[session_key]['started_at'],
            'marked_count': len(recognition_sessions[session_key]['marked_today'])
        }
    return {'active': False}

def start_recognition_session(user_id, project_id, embeddings_list, attendance_mode='daily'):
    """Start recognition session programmatically from recognize.py
    
    Args:
        user_id: User ID
        project_id: Project ID
        embeddings_list: List of {name, embedding} dicts from DB
        attendance_mode: 'daily' or other mode
    
    Returns:
        True if session started, False if already running
    """
    session_key = f"{user_id}_{project_id}"
    
    if session_key in recognition_sessions:
        return False  # Already running
    
    recognition_sessions[session_key] = {
        'user_id': user_id,
        'project_id': project_id,
        'embeddings': embeddings_list,
        'attendance_mode': attendance_mode,
        'marked_today': set(),
        'started_at': datetime.now().isoformat()
    }
    
    return True

def stop_recognition_session(user_id, project_id):
    """Allows programmatic stop if needed by recognize.py"""
    session_key = f"{user_id}_{project_id}"
    if session_key in recognition_sessions:
        del recognition_sessions[session_key]
        return True
    return False
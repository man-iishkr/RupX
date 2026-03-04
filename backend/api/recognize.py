from flask import Blueprint, request, jsonify, session
import json
import numpy as np
from datetime import datetime
from utils.db import get_db

bp = Blueprint('recognize', __name__)

# In-memory session store (works since we only have 1 gunicorn worker)
recognition_sessions = {}

def get_active_project():
    """Get active project for current user"""
    if 'user_id' not in session:
        return None
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, user_id, attendance_mode, model_trained, embeddings_data, attendance_names
        FROM projects 
        WHERE user_id = ? AND is_active = 1
    ''', (session['user_id'],))
    
    project = cursor.fetchone()
    conn.close()
    
    return dict(project) if project else None

def cosine_similarity(emb1, emb2):
    """Calculate cosine similarity"""
    dot_product = np.dot(emb1, emb2)
    norm_a = np.linalg.norm(emb1)
    norm_b = np.linalg.norm(emb2)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(dot_product / (norm_a * norm_b))

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
        return True
    except Exception as e:
        print(f"❌ Failed to mark attendance: {str(e)}")
        return False

@bp.route('/start', methods=['POST'])
def start_recognition():
    """Start face recognition session - loads embeddings into memory for fast REST matching"""
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    project = get_active_project()
    if not project:
        return jsonify({'error': 'No active project'}), 400
    
    try:
        user_id = session['user_id']
        project_id = project['id']
        
        # Check if model is trained
        if not project.get('model_trained'):
            return jsonify({'error': 'Model not trained yet'}), 400
        
        # Check if embeddings exist in database
        embeddings_raw = project.get('embeddings_data')
        if not embeddings_raw:
            return jsonify({'error': 'No embeddings found. Please train the model first.'}), 400
        
        # Parse embeddings from database
        try:
            embeddings_data = json.loads(embeddings_raw)
        except (json.JSONDecodeError, TypeError):
            return jsonify({'error': 'Corrupted embeddings data. Please retrain the model.'}), 400
        
        if not embeddings_data.get('embeddings') or len(embeddings_data['embeddings']) == 0:
            return jsonify({'error': 'No valid embeddings found. Please retrain the model.'}), 400
        
        # Initialize session in memory
        session_key = f"{user_id}_{project_id}"
        
        recognition_sessions[session_key] = {
            'user_id': user_id,
            'project_id': project_id,
            'embeddings': embeddings_data['embeddings'],
            'attendance_mode': project.get('attendance_mode', 'daily'),
            'marked_today': set(),
            'started_at': datetime.now().isoformat()
        }
        
        return jsonify({'success': True, 'message': 'Recognition started', 'num_identities': len(embeddings_data['embeddings'])}), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/stop', methods=['POST'])
def stop_recognition():
    """Stop face recognition session and clear from memory"""
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    project = get_active_project()
    if not project:
        return jsonify({'error': 'No active project'}), 400
    
    try:
        user_id = session['user_id']
        project_id = project['id']
        session_key = f"{user_id}_{project_id}"
        
        if session_key in recognition_sessions:
            del recognition_sessions[session_key]
        
        return jsonify({'success': True, 'message': 'Recognition stopped'}), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/status', methods=['GET'])
def recognition_status():
    """Get recognition session status"""
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    project = get_active_project()
    if not project:
        return jsonify({'error': 'No active project'}), 400
    
    try:
        user_id = session['user_id']
        project_id = project['id']
        session_key = f"{user_id}_{project_id}"
        
        if session_key in recognition_sessions:
            return jsonify({
                'active': True,
                'started_at': recognition_sessions[session_key]['started_at'],
                'marked_count': len(recognition_sessions[session_key]['marked_today'])
            }), 200
        return jsonify({'active': False}), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/frame', methods=['POST'])
def recognize_frame():
    """REST endpoint for processing a single frame embedding"""
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
        
    data = request.get_json()
    if not data or 'embedding' not in data:
        return jsonify({'error': 'Missing embedding data'}), 400
        
    project = get_active_project()
    if not project:
        return jsonify({'error': 'No active project'}), 400
        
    user_id = session['user_id']
    project_id = project['id']
    session_key = f"{user_id}_{project_id}"
    
    if session_key not in recognition_sessions:
        return jsonify({'error': 'Recognition session not active'}), 400
        
    session_data = recognition_sessions[session_key]
    embedding = data['embedding']
    
    try:
        detected_embedding = np.array(embedding, dtype=np.float32)
        if detected_embedding.shape[0] not in [128, 512]:
            return jsonify({'error': f'Invalid dimension: {detected_embedding.shape[0]}'}), 400
            
        detected_embedding = detected_embedding / np.linalg.norm(detected_embedding)
    except Exception as e:
        return jsonify({'error': f'Failed to parse embedding: {str(e)}'}), 400
        
    recognized_persons = []
    
    for stored_person in session_data['embeddings']:
        stored_embedding = np.array(stored_person['embedding'], dtype=np.float32)
        stored_embedding = stored_embedding / np.linalg.norm(stored_embedding)
        
        similarity = cosine_similarity(detected_embedding, stored_embedding)
        threshold = 0.8 if detected_embedding.shape[0] == 128 else 0.6
        
        if similarity > threshold:
            person_name = stored_person['name']
            today = datetime.now().strftime('%Y-%m-%d')
            mark_key = f"{person_name}_{today}"
            
            newly_marked = False
            if mark_key not in session_data['marked_today']:
                success = mark_attendance_db(person_name, project_id)
                if success:
                    session_data['marked_today'].add(mark_key)
                    newly_marked = True
                    
            recognized_persons.append({
                'name': person_name,
                'confidence': float(similarity),
                'timestamp': datetime.now().isoformat(),
                'newly_marked': newly_marked
            })
            
    return jsonify({'success': True, 'persons': recognized_persons}), 200

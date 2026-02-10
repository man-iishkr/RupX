from flask import Blueprint, request, jsonify, session
import json
from utils.db import get_db
from websocket.video_stream import get_recognition_status, start_recognition_session, stop_recognition_session

bp = Blueprint('recognize', __name__)

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

@bp.route('/start', methods=['POST'])
def start_recognition():
    """Start face recognition session - uses DB-stored embeddings"""
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
        
        # Start recognition session with DB-loaded embeddings
        success = start_recognition_session(
            user_id, project_id,
            embeddings_data['embeddings'],
            project.get('attendance_mode', 'daily')
        )
        
        if success:
            return jsonify({'success': True, 'message': 'Recognition started'}), 200
        else:
            return jsonify({'error': 'Recognition already running'}), 400
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/stop', methods=['POST'])
def stop_recognition():
    """Stop face recognition session"""
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    project = get_active_project()
    if not project:
        return jsonify({'error': 'No active project'}), 400
    
    try:
        user_id = session['user_id']
        project_id = project['id']
        
        stop_recognition_session(user_id, project_id)
        
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
        
        status = get_recognition_status(user_id, project_id)
        
        return jsonify(status), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

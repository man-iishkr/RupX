from flask import Blueprint, request, jsonify, session
import os
from utils.db_init import get_db
from websocket.video_stream import get_recognition_status, start_recognition_session, stop_recognition_session

bp = Blueprint('recognize', __name__)

def get_active_project():
    """Get active project for current user"""
    if 'user_id' not in session:
        return None
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, user_id, attendance_mode FROM projects 
        WHERE user_id = ? AND is_active = 1
    ''', (session['user_id'],))
    
    project = cursor.fetchone()
    conn.close()
    
    return dict(project) if project else None

@bp.route('/start', methods=['POST'])
def start_recognition():
    """Start face recognition session"""
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    project = get_active_project()
    if not project:
        return jsonify({'error': 'No active project'}), 400
    
    try:
        user_id = session['user_id']
        project_id = project['id']
        
        # Check if model trained
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT model_trained FROM projects WHERE id = ?', (project_id,))
        result = cursor.fetchone()
        conn.close()
        
        if not result or not result['model_trained']:
            return jsonify({'error': 'Model not trained yet'}), 400
        
        # Check embeddings file
        embeddings_path = f'storage/users/{user_id}/projects/{project_id}/models/embeddings.npy'
        if not os.path.exists(embeddings_path):
            return jsonify({'error': 'Model file not found'}), 400
        
        # Check attendance file
        attendance_path = f'storage/users/{user_id}/projects/{project_id}/attendance/attendance.xlsx'
        if not os.path.exists(attendance_path):
            return jsonify({'error': 'Attendance file not found'}), 400
        
        # Start recognition
        success = start_recognition_session(user_id, project_id, embeddings_path, 
                                           attendance_path, project['attendance_mode'])
        
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
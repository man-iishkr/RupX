from flask import Blueprint, request, jsonify, session
import os
import threading
import time
from datetime import datetime
import numpy as np
from utils.db_init import get_db
from ml.face_embedding import train_embeddings
import pandas as pd

bp = Blueprint('train', __name__)

# Global training status
training_status = {}
training_lock = threading.Lock()

def get_active_project():
    """Get active project for current user"""
    if 'user_id' not in session:
        return None
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, user_id FROM projects 
        WHERE user_id = ? AND is_active = 1
    ''', (session['user_id'],))
    
    project = cursor.fetchone()
    conn.close()
    
    return dict(project) if project else None

def training_worker(user_id, project_id, dataset_dir, models_dir):
    """Background training thread"""
    global training_status
    
    key = f"{user_id}_{project_id}"
    start_time = time.time()
    
    try:
        # Update status
        with training_lock:
            training_status[key] = {
                'status': 'running',
                'progress': 0,
                'message': 'Initializing...',
                'identities': 0,
                'processed': 0,
                'skipped': 0
            }
        
        # Log training start
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO training_logs 
            (project_id, started_at, status) 
            VALUES (?, ?, ?)
        ''', (project_id, datetime.now().isoformat(), 'running'))
        conn.commit()
        log_id = cursor.lastrowid
        conn.close()
        
        # Train embeddings
        result = train_embeddings(
            dataset_dir=dataset_dir,
            output_path=f'{models_dir}/embeddings.npy',
            progress_callback=lambda p, msg: update_training_progress(key, p, msg)
        )
        
        duration = time.time() - start_time
        
        if result['success']:
            # Update project
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE projects 
                SET model_trained = 1 
                WHERE id = ?
            ''', (project_id,))
            
            # Update training log with metrics
            metrics = result.get('metrics', {})
            cursor.execute('''
                UPDATE training_logs 
                SET completed_at = ?, status = ?, 
                    num_identities = ?, images_processed = ?, 
                    images_skipped = ?, duration_seconds = ?,
                    accuracy = ?, precision = ?
                WHERE id = ?
            ''', (
                datetime.now().isoformat(),
                'completed',
                result['identities'],
                result['processed'],
                result['skipped'],
                duration,
                metrics.get('accuracy', 0),
                metrics.get('precision', 0),
                log_id
            ))
            conn.commit()
            conn.close()
            
            # Create attendance file
            create_attendance_file(user_id, project_id, result['names'])
            
            # Update status
            with training_lock:
                training_status[key] = {
                    'status': 'completed',
                    'progress': 100,
                    'message': 'Training completed successfully',
                    'identities': result['identities'],
                    'processed': result['processed'],
                    'skipped': result['skipped'],
                    'duration': duration
                }
        else:
            # Training failed
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE training_logs 
                SET completed_at = ?, status = ?, error_message = ?,
                    duration_seconds = ?
                WHERE id = ?
            ''', (
                datetime.now().isoformat(),
                'failed',
                result.get('error', 'Unknown error'),
                duration,
                log_id
            ))
            conn.commit()
            conn.close()
            
            with training_lock:
                training_status[key] = {
                    'status': 'failed',
                    'progress': 0,
                    'message': result.get('error', 'Training failed'),
                    'identities': 0,
                    'processed': 0,
                    'skipped': 0
                }
    
    except Exception as e:
        # Exception handling
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE training_logs 
            SET completed_at = ?, status = ?, error_message = ?
            WHERE id = ?
        ''', (
            datetime.now().isoformat(),
            'failed',
            str(e),
            log_id
        ))
        conn.commit()
        conn.close()
        
        with training_lock:
            training_status[key] = {
                'status': 'failed',
                'progress': 0,
                'message': str(e),
                'identities': 0,
                'processed': 0,
                'skipped': 0
            }

def update_training_progress(key, progress, message):
    """Update training progress"""
    with training_lock:
        if key in training_status:
            training_status[key]['progress'] = progress
            training_status[key]['message'] = message

def create_attendance_file(user_id, project_id, names):
    """Create Excel attendance file with names"""
    attendance_dir = f'storage/users/{user_id}/projects/{project_id}/attendance'
    os.makedirs(attendance_dir, exist_ok=True)
    
    file_path = f'{attendance_dir}/attendance.xlsx'
    
    # Create DataFrame with names
    df = pd.DataFrame({'NAME': sorted(names)})
    df.to_excel(file_path, index=False, engine='openpyxl')

@bp.route('/start', methods=['POST'])
def start_training():
    """Start model training"""
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    project = get_active_project()
    if not project:
        return jsonify({'error': 'No active project'}), 400
    
    try:
        user_id = session['user_id']
        project_id = project['id']
        key = f"{user_id}_{project_id}"
        
        # Check if already training
        with training_lock:
            if key in training_status and training_status[key]['status'] == 'running':
                return jsonify({'error': 'Training already in progress'}), 400
        
        # Check dataset
        dataset_dir = f'storage/users/{user_id}/projects/{project_id}/dataset'
        if not os.path.exists(dataset_dir) or not os.listdir(dataset_dir):
            return jsonify({'error': 'No dataset uploaded'}), 400
        
        models_dir = f'storage/users/{user_id}/projects/{project_id}/models'
        os.makedirs(models_dir, exist_ok=True)
        
        # Start training thread
        thread = threading.Thread(
            target=training_worker,
            args=(user_id, project_id, dataset_dir, models_dir),
            daemon=True
        )
        thread.start()
        
        return jsonify({'success': True, 'message': 'Training started'}), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/progress', methods=['GET'])
def training_progress():
    """Get training progress"""
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    project = get_active_project()
    if not project:
        return jsonify({'error': 'No active project'}), 400
    
    key = f"{session['user_id']}_{project['id']}"
    
    with training_lock:
        if key in training_status:
            return jsonify(training_status[key]), 200
        else:
            return jsonify({
                'status': 'idle',
                'progress': 0,
                'message': 'No training in progress'
            }), 200

@bp.route('/status', methods=['GET'])
def model_status():
    """Get model training status"""
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    project = get_active_project()
    if not project:
        return jsonify({'error': 'No active project'}), 400
    
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Get project status
        cursor.execute('''
            SELECT dataset_uploaded, model_trained 
            FROM projects 
            WHERE id = ?
        ''', (project['id'],))
        
        result = cursor.fetchone()
        
        # Get latest training log
        cursor.execute('''
            SELECT * FROM training_logs 
            WHERE project_id = ? 
            ORDER BY started_at DESC 
            LIMIT 1
        ''', (project['id'],))
        
        latest_log = cursor.fetchone()
        conn.close()
        
        response = {
            'dataset_uploaded': bool(result['dataset_uploaded']),
            'model_trained': bool(result['model_trained']),
            'latest_training': None
        }
        
        if latest_log:
            response['latest_training'] = {
                'status': latest_log['status'],
                'started_at': latest_log['started_at'],
                'completed_at': latest_log['completed_at'],
                'identities': latest_log['num_identities'],
                'processed': latest_log['images_processed'],
                'skipped': latest_log['images_skipped'],
                'duration': latest_log['duration_seconds']
            }
        
        return jsonify(response), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/history', methods=['GET'])
def training_history():
    """Get training history"""
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    project = get_active_project()
    if not project:
        return jsonify({'error': 'No active project'}), 400
    
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM training_logs 
            WHERE project_id = ? 
            ORDER BY started_at DESC 
            LIMIT 10
        ''', (project['id'],))
        
        logs = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        return jsonify({'logs': logs}), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500
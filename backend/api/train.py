"""
Training API Routes
Modified: Returns dataset info for client-side training instead of training on server
"""

from flask import Blueprint, request, jsonify, session
from functools import wraps
import os
import json
import zipfile
import shutil
from datetime import datetime
from utils.db import get_db
import pandas as pd

bp = Blueprint('train', __name__)

def require_auth(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'error': 'Not authenticated'}), 401
        return f(*args, **kwargs)
    return decorated_function

def get_active_project():
    if 'user_id' not in session:
        return None
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        'SELECT * FROM projects WHERE user_id = ? AND is_active = 1',
        (session['user_id'],)
    )
    project = cursor.fetchone()
    return dict(project) if project else None

@bp.route('/start', methods=['POST'])
@require_auth
def start_training():
    """Start training - returns dataset info for client processing"""
    project = get_active_project()
    if not project:
        return jsonify({'error': 'No active project'}), 400
    
    if not project['dataset_uploaded']:
        return jsonify({'error': 'No dataset uploaded. Please upload dataset first.'}), 400
    
    dataset_dir = f'storage/users/{session["user_id"]}/projects/{project["id"]}/dataset'
    
    if not os.path.exists(dataset_dir):
        return jsonify({'error': 'Dataset directory not found'}), 404
    
    # Scan dataset
    person_folders = [f for f in os.listdir(dataset_dir) 
                     if os.path.isdir(os.path.join(dataset_dir, f))]
    
    if len(person_folders) == 0:
        return jsonify({'error': 'No person folders found in dataset'}), 400
    
    persons_info = []
    total_images = 0
    
    for person_name in person_folders:
        person_path = os.path.join(dataset_dir, person_name)
        images = [f for f in os.listdir(person_path) 
                 if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
        
        if len(images) < 10:
            continue
        
        selected_images = images[:20]  # Limit to 20 per person
        
        persons_info.append({
            'name': person_name,
            'image_count': len(images),
            'images': selected_images
        })
        total_images += len(selected_images)
    
    # Log training start
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        'INSERT INTO training_logs (project_id, started_at, status, num_identities) '
        'VALUES (?, ?, ?, ?)',
        (project['id'], datetime.now().isoformat(), 'client_training', len(persons_info))
    )
    conn.commit()
    
    return jsonify({
        'success': True,
        'message': 'Dataset ready for browser training',
        'dataset': {
            'total_persons': len(persons_info),
            'total_images': total_images,
            'persons': persons_info,
            'base_url': f'/api/dataset/images/{project["id"]}'
        }
    }), 200

@bp.route('/save', methods=['POST'])
@require_auth
def save_embeddings():
    """Save embeddings received from client"""
    project = get_active_project()
    if not project:
        return jsonify({'error': 'No active project'}), 400
    
    data = request.get_json()
    
    if not data or 'embeddings' not in data:
        return jsonify({'error': 'Missing embeddings data'}), 400
    
    embeddings_data = data['embeddings']
    metadata = data.get('metadata', {})
    
    if not isinstance(embeddings_data, list) or len(embeddings_data) == 0:
        return jsonify({'error': 'Invalid embeddings format'}), 400
    
    for item in embeddings_data:
        if 'name' not in item or 'embedding' not in item:
            return jsonify({'error': 'Each embedding must have name and embedding'}), 400
    
    # Save as JSON
    models_dir = f'storage/users/{session["user_id"]}/projects/{project["id"]}/models'
    os.makedirs(models_dir, exist_ok=True)
    
    embeddings_file = os.path.join(models_dir, 'embeddings.json')
    
    with open(embeddings_file, 'w') as f:
        json.dump({
            'embeddings': embeddings_data,
            'metadata': {
                **metadata,
                'created_at': datetime.now().isoformat(),
                'training_mode': 'client_side'
            }
        }, f, indent=2)
    
    # Update project
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        'UPDATE projects SET model_trained = 1 WHERE id = ?',
        (project['id'],)
    )
    
    # Update training log
    cursor.execute(
        'UPDATE training_logs SET completed_at = ?, status = ?, images_processed = ? '
        'WHERE project_id = ? AND status = "client_training" '
        'ORDER BY started_at DESC LIMIT 1',
        (datetime.now().isoformat(), 'completed', 
         metadata.get('total_images_processed', 0), project['id'])
    )
    conn.commit()
    
    # Create attendance file
    names = [item['name'] for item in embeddings_data]
    create_attendance_file(session['user_id'], project['id'], names)
    
    return jsonify({
        'success': True,
        'message': 'Model trained successfully',
        'num_identities': len(embeddings_data)
    }), 200

@bp.route('/progress', methods=['GET'])
@require_auth
def get_progress():
    """Get training progress"""
    project = get_active_project()
    if not project:
        return jsonify({'error': 'No active project'}), 400
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        'SELECT * FROM training_logs WHERE project_id = ? '
        'ORDER BY started_at DESC LIMIT 1',
        (project['id'],)
    )
    log = cursor.fetchone()
    
    if not log:
        return jsonify({
            'status': 'idle',
            'message': 'No training started'
        }), 200
    
    return jsonify({
        'status': log['status'],
        'started_at': log['started_at'],
        'completed_at': log['completed_at'],
        'num_identities': log['num_identities'],
        'message': 'Training in browser' if log['status'] == 'client_training' else 'Completed'
    }), 200

@bp.route('/status', methods=['GET'])
@require_auth
def get_status():
    """Get training status"""
    project = get_active_project()
    if not project:
        return jsonify({'error': 'No active project'}), 400
    
    models_dir = f'storage/users/{session["user_id"]}/projects/{project["id"]}/models'
    embeddings_file = os.path.join(models_dir, 'embeddings.json')
    
    model_trained = os.path.exists(embeddings_file)
    
    result = {
        'dataset_uploaded': project['dataset_uploaded'],
        'model_trained': model_trained
    }
    
    if model_trained:
        try:
            with open(embeddings_file, 'r') as f:
                data = json.load(f)
                result['latest_training'] = {
                    'num_identities': len(data['embeddings']),
                    'created_at': data['metadata'].get('created_at')
                }
        except:
            pass
    
    return jsonify(result), 200

def create_attendance_file(user_id, project_id, names):
    """Create attendance Excel file"""
    attendance_dir = f'storage/users/{user_id}/projects/{project_id}/attendance'
    os.makedirs(attendance_dir, exist_ok=True)
    
    file_path = f'{attendance_dir}/attendance.xlsx'
    df = pd.DataFrame({'NAME': sorted(names)})
    df.to_excel(file_path, index=False, engine='openpyxl')
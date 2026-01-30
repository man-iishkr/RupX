"""
Training API Routes
Modified: Returns dataset info from Cloudinary for client-side training
"""

from flask import Blueprint, request, jsonify, session
from functools import wraps
import os
import json
from datetime import datetime
from utils.db import get_db
import pandas as pd
import cloudinary.api
from dotenv import load_dotenv

load_dotenv()

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
    conn.close()
    return dict(project) if project else None

@bp.route('/start', methods=['POST'])
@require_auth
def start_training():
    """
    Start training - MODIFIED FOR CLOUDINARY
    Returns dataset info from Cloudinary cloud storage
    """
    project = get_active_project()
    if not project:
        return jsonify({'error': 'No active project'}), 400
    
    if not project['dataset_uploaded']:
        return jsonify({'error': 'No dataset uploaded. Please upload dataset first.'}), 400
    
    # Get Cloudinary folder
    cloudinary_folder = project.get('cloudinary_folder')
    if not cloudinary_folder:
        return jsonify({'error': 'Dataset not found in cloud storage'}), 404
    
    try:
        # Fetch images from Cloudinary
        resources = cloudinary.api.resources(
            type="upload",
            prefix=cloudinary_folder,
            max_results=500
        )
        
        # Group by person
        persons_dict = {}
        for resource in resources.get('resources', []):
            path_parts = resource['public_id'].split('/')
            if len(path_parts) >= 4:
                person_name = path_parts[-2]
                image_name = path_parts[-1] + '.jpg'
                
                if person_name not in persons_dict:
                    persons_dict[person_name] = []
                
                persons_dict[person_name].append(image_name)
        
        # Build persons info
        persons_info = []
        total_images = 0
        
        for person_name, images in persons_dict.items():
            if len(images) < 10:
                continue
            
            selected_images = images[:20]
            persons_info.append({
                'name': person_name,
                'image_count': len(images),
                'images': selected_images
            })
            total_images += len(selected_images)
        
        if len(persons_info) == 0:
            return jsonify({'error': 'No valid persons found'}), 400
        
        # Log training start
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO training_logs (project_id, started_at, status, num_identities) '
            'VALUES (?, ?, ?, ?)',
            (project['id'], datetime.now().isoformat(), 'client_training', len(persons_info))
        )
        conn.commit()
        conn.close()
        
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
        
    except Exception as e:
        print(f"Error fetching from Cloudinary: {e}")
        return jsonify({'error': f'Failed to fetch dataset: {str(e)}'}), 500

@bp.route('/save', methods=['POST'])
@require_auth
def save_embeddings():
    """Save embeddings received from client - MODIFIED: Auto-delete images after training"""
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
    
    # Save embeddings in database as JSON
    embeddings_json = json.dumps({
        'embeddings': embeddings_data,
        'metadata': {
            **metadata,
            'created_at': datetime.now().isoformat(),
            'training_mode': 'client_side'
        }
    })
    
    # Update project with embeddings
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE projects 
        SET model_trained = 1,
            embeddings_data = ?
        WHERE id = ?
    ''', (embeddings_json, project['id']))
    
    # Update training log
    cursor.execute('''
        UPDATE training_logs 
        SET completed_at = ?, status = ?, images_processed = ?
        WHERE project_id = ? AND status = "client_training"
        ORDER BY started_at DESC LIMIT 1
    ''', (datetime.now().isoformat(), 'completed', 
         metadata.get('total_images_processed', 0), project['id']))
    
    conn.commit()
    conn.close()
    
    # Create attendance file reference
    names = [item['name'] for item in embeddings_data]
    create_attendance_reference(session['user_id'], project['id'], names)
    
    # 🎯 NEW: Delete images from Cloudinary after successful training
    cloudinary_folder = project.get('cloudinary_folder')
    if cloudinary_folder:
        try:
            delete_success = delete_cloudinary_images(cloudinary_folder)
            print(f"✅ Cloudinary cleanup: {'Success' if delete_success else 'Failed'}")
        except Exception as e:
            print(f"⚠️ Cloudinary cleanup error: {e}")
            # Don't fail the request if cleanup fails
    
    return jsonify({
        'success': True,
        'message': 'Model trained successfully! Training images have been removed to save storage.',
        'num_identities': len(embeddings_data),
        'storage_cleaned': True
    }), 200

@bp.route('/progress', methods=['GET'])
@require_auth
def get_progress():
    """Get training progress - UNCHANGED"""
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
    conn.close()
    
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
    """Get training status - MODIFIED for database storage"""
    project = get_active_project()
    if not project:
        return jsonify({'error': 'No active project'}), 400
    
    model_trained = bool(project.get('model_trained'))
    
    result = {
        'dataset_uploaded': bool(project['dataset_uploaded']),
        'model_trained': model_trained
    }
    
    if model_trained and project.get('embeddings_data'):
        try:
            embeddings_data = json.loads(project['embeddings_data'])
            result['latest_training'] = {
                'num_identities': len(embeddings_data.get('embeddings', [])),
                'created_at': embeddings_data.get('metadata', {}).get('created_at')
            }
        except:
            pass
    
    return jsonify(result), 200

def create_attendance_reference(user_id, project_id, names):
    """Store attendance template in database - no file system needed"""
    conn = get_db()
    cursor = conn.cursor()
    
    # Store names as JSON in database
    cursor.execute('''
        UPDATE projects
        SET attendance_names = ?
        WHERE id = ?
    ''', (json.dumps(sorted(names)), project_id))
    
    conn.commit()
    conn.close()

def delete_cloudinary_images(cloudinary_folder):
    """
    Delete all images from Cloudinary after successful training
    This saves storage space - embeddings are all we need for recognition
    """
    try:
        print(f"🗑️  Deleting images from Cloudinary: {cloudinary_folder}")
        
        # Get all resources in this folder
        resources = cloudinary.api.resources(
            type="upload",
            prefix=cloudinary_folder,
            max_results=500
        )
        
        deleted_count = 0
        
        # Delete each image
        for resource in resources.get('resources', []):
            public_id = resource['public_id']
            try:
                cloudinary.uploader.destroy(public_id)
                deleted_count += 1
            except Exception as e:
                print(f"⚠️  Failed to delete {public_id}: {e}")
        
        # If more than 500 images, paginate
        while 'next_cursor' in resources:
            resources = cloudinary.api.resources(
                type="upload",
                prefix=cloudinary_folder,
                max_results=500,
                next_cursor=resources['next_cursor']
            )
            
            for resource in resources.get('resources', []):
                public_id = resource['public_id']
                try:
                    cloudinary.uploader.destroy(public_id)
                    deleted_count += 1
                except Exception as e:
                    print(f"⚠️  Failed to delete {public_id}: {e}")
        
        print(f"✅ Deleted {deleted_count} images from Cloudinary")
        return True
        
    except Exception as e:
        print(f"❌ Error deleting Cloudinary images: {e}")
        return False
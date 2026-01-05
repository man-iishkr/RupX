from flask import Blueprint, request, jsonify, session
import os
import zipfile
import shutil
from werkzeug.utils import secure_filename
from PIL import Image
from utils.db import get_db

bp = Blueprint('dataset', __name__)

ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

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

@bp.route('/upload', methods=['POST'])
def upload_dataset():
    """Upload dataset ZIP file"""
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    project = get_active_project()
    if not project:
        return jsonify({'error': 'No active project'}), 400
    
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    if not file.filename.endswith('.zip'):
        return jsonify({'error': 'Only ZIP files allowed'}), 400
    
    try:
        project_id = project['id']
        user_id = session['user_id']
        dataset_dir = f'storage/users/{user_id}/projects/{project_id}/dataset'
        
        # Clear existing dataset
        if os.path.exists(dataset_dir):
            shutil.rmtree(dataset_dir)
        os.makedirs(dataset_dir, exist_ok=True)
        
        # Save and extract ZIP
        zip_path = f'{dataset_dir}/upload.zip'
        file.save(zip_path)
        
        # Extract
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(dataset_dir)
        
        os.remove(zip_path)
        
        # Validate structure
        validation_result = validate_dataset(dataset_dir)
        
        if not validation_result['valid']:
            shutil.rmtree(dataset_dir)
            os.makedirs(dataset_dir)
            return jsonify({
                'error': validation_result['message'],
                'details': validation_result.get('details', {})
            }), 400
        
        # Update database
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE projects 
            SET dataset_uploaded = 1, model_trained = 0 
            WHERE id = ?
        ''', (project_id,))
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'stats': validation_result['stats']
        }), 200
        
    except zipfile.BadZipFile:
        return jsonify({'error': 'Invalid ZIP file'}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def validate_dataset(dataset_dir):
    """Validate dataset structure and contents"""
    try:
        # Find root directory (handle extra nesting)
        contents = os.listdir(dataset_dir)
        
        # If single folder, treat as root
        if len(contents) == 1 and os.path.isdir(os.path.join(dataset_dir, contents[0])):
            root_dir = os.path.join(dataset_dir, contents[0])
        else:
            root_dir = dataset_dir
        
        # Get person folders
        person_folders = [f for f in os.listdir(root_dir) 
                         if os.path.isdir(os.path.join(root_dir, f)) and not f.startswith('.')]
        
        if len(person_folders) == 0:
            return {
                'valid': False,
                'message': 'No person folders found. Expected structure: Person_Name/images.jpg'
            }
        
        total_images = 0
        valid_persons = 0
        invalid_persons = []
        
        for person in person_folders:
            person_path = os.path.join(root_dir, person)
            images = [f for f in os.listdir(person_path) 
                     if allowed_file(f) and os.path.isfile(os.path.join(person_path, f))]
            
            # Validate images
            valid_images = 0
            for img_file in images:
                img_path = os.path.join(person_path, img_file)
                try:
                    img = Image.open(img_path)
                    img.verify()
                    valid_images += 1
                except:
                    os.remove(img_path)
            
            if valid_images < 10:
                invalid_persons.append({
                    'name': person,
                    'images': valid_images,
                    'required': 10
                })
            else:
                valid_persons += 1
                total_images += valid_images
        
        if valid_persons == 0:
            return {
                'valid': False,
                'message': 'No valid persons found. Each person needs minimum 10 images',
                'details': {'invalid_persons': invalid_persons}
            }
        
        # Move to correct location if nested
        if root_dir != dataset_dir:
            for person in person_folders:
                if os.path.exists(os.path.join(root_dir, person)):
                    shutil.move(
                        os.path.join(root_dir, person),
                        os.path.join(dataset_dir, person)
                    )
            # Remove extracted folder
            if os.path.exists(root_dir):
                shutil.rmtree(root_dir)
        
        return {
            'valid': True,
            'stats': {
                'total_persons': valid_persons,
                'total_images': total_images,
                'invalid_persons': len(invalid_persons)
            }
        }
        
    except Exception as e:
        return {
            'valid': False,
            'message': f'Validation error: {str(e)}'
        }

@bp.route('/status', methods=['GET'])
def dataset_status():
    """Get dataset upload status"""
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    project = get_active_project()
    if not project:
        return jsonify({'error': 'No active project'}), 400
    
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT dataset_uploaded, model_trained 
            FROM projects 
            WHERE id = ?
        ''', (project['id'],))
        
        result = cursor.fetchone()
        conn.close()
        
        if not result:
            return jsonify({'error': 'Project not found'}), 404
        
        dataset_dir = f'storage/users/{session["user_id"]}/projects/{project["id"]}/dataset'
        
        stats = None
        if result['dataset_uploaded'] and os.path.exists(dataset_dir):
            person_folders = [f for f in os.listdir(dataset_dir) 
                            if os.path.isdir(os.path.join(dataset_dir, f))]
            
            total_images = 0
            for person in person_folders:
                person_path = os.path.join(dataset_dir, person)
                images = [f for f in os.listdir(person_path) if allowed_file(f)]
                total_images += len(images)
            
            stats = {
                'total_persons': len(person_folders),
                'total_images': total_images
            }
        
        return jsonify({
            'uploaded': bool(result['dataset_uploaded']),
            'trained': bool(result['model_trained']),
            'stats': stats
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500
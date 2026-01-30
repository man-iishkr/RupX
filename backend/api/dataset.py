"""
Dataset API - Modified for Cloudinary Storage
CHANGES: Upload images to Cloudinary instead of local filesystem
PRESERVED: All validation logic, all other functions
"""

from flask import Blueprint, request, jsonify, session
import os
import zipfile
import shutil
import tempfile
from werkzeug.utils import secure_filename
from PIL import Image
from utils.db import get_db
import cloudinary
import cloudinary.uploader
from dotenv import load_dotenv

load_dotenv()

# Configure Cloudinary
cloudinary.config(
    cloud_name=os.getenv('CLOUDINARY_CLOUD_NAME'),
    api_key=os.getenv('CLOUDINARY_API_KEY'),
    api_secret=os.getenv('CLOUDINARY_API_SECRET'),
    secure=True
)

bp = Blueprint('dataset', __name__)

ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_active_project():
    """Get active project for current user - UNCHANGED"""
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
    """
    Upload dataset ZIP file - MODIFIED FOR CLOUDINARY
    Now uploads images to Cloudinary instead of local storage
    """
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
    
    # Use temporary directory for processing
    temp_dir = tempfile.mkdtemp()
    
    try:
        project_id = project['id']
        user_id = session['user_id']
        
        # Save ZIP to temp location
        zip_path = os.path.join(temp_dir, 'upload.zip')
        file.save(zip_path)
        
        # Extract ZIP
        extract_dir = os.path.join(temp_dir, 'extracted')
        os.makedirs(extract_dir, exist_ok=True)
        
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(extract_dir)
        
        # Validate structure
        validation_result = validate_dataset(extract_dir)
        
        if not validation_result['valid']:
            return jsonify({
                'error': validation_result['message'],
                'details': validation_result.get('details', {})
            }), 400
        
        # Upload validated images to Cloudinary
        cloudinary_folder = f"rupx/{user_id}/project_{project_id}"
        uploaded_count = upload_to_cloudinary(extract_dir, cloudinary_folder)
        
        if uploaded_count == 0:
            return jsonify({'error': 'Failed to upload images to cloud storage'}), 500
        
        # Update database
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE projects 
            SET dataset_uploaded = 1, model_trained = 0,
                cloudinary_folder = ?
            WHERE id = ?
        ''', (cloudinary_folder, project_id))
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'stats': validation_result['stats']
        }), 200
        
    except zipfile.BadZipFile:
        return jsonify({'error': 'Invalid ZIP file'}), 400
    except Exception as e:
        print(f"Upload error: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        # Cleanup temp directory
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)

def upload_to_cloudinary(dataset_dir, cloudinary_folder):
    """
    Upload all images to Cloudinary
    NEW FUNCTION - handles cloud upload
    """
    uploaded_count = 0
    
    # Find person folders
    contents = os.listdir(dataset_dir)
    
    if len(contents) == 1 and os.path.isdir(os.path.join(dataset_dir, contents[0])):
        root_dir = os.path.join(dataset_dir, contents[0])
    else:
        root_dir = dataset_dir
    
    person_folders = [f for f in os.listdir(root_dir) 
                     if os.path.isdir(os.path.join(root_dir, f)) and not f.startswith('.')]
    
    for person in person_folders:
        person_path = os.path.join(root_dir, person)
        images = [f for f in os.listdir(person_path) if allowed_file(f)]
        
        for img_file in images:
            img_path = os.path.join(person_path, img_file)
            
            try:
                # Upload to Cloudinary with structured path
                result = cloudinary.uploader.upload(
                    img_path,
                    folder=f"{cloudinary_folder}/{person}",
                    public_id=os.path.splitext(img_file)[0],
                    resource_type="image",
                    overwrite=True
                )
                uploaded_count += 1
                print(f"✅ Uploaded: {person}/{img_file}")
            except Exception as e:
                print(f"⚠️ Failed to upload {img_file}: {e}")
    
    return uploaded_count

def validate_dataset(dataset_dir):
    """Validate dataset structure - UNCHANGED"""
    try:
        contents = os.listdir(dataset_dir)
        
        if len(contents) == 1 and os.path.isdir(os.path.join(dataset_dir, contents[0])):
            root_dir = os.path.join(dataset_dir, contents[0])
        else:
            root_dir = dataset_dir
        
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
            
            valid_images = 0
            for img_file in images:
                img_path = os.path.join(person_path, img_file)
                try:
                    img = Image.open(img_path)
                    img.verify()
                    valid_images += 1
                except:
                    pass
            
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

@bp.route('/images/<int:project_id>/<person>/<image>', methods=['GET'])
def get_image(project_id, person, image):
    """
    Get image URL from Cloudinary
    NEW ENDPOINT - returns Cloudinary URL instead of serving file
    """
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    try:
        # Get project's Cloudinary folder
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT cloudinary_folder FROM projects 
            WHERE id = ? AND user_id = ?
        ''', (project_id, session['user_id']))
        
        result = cursor.fetchone()
        conn.close()
        
        if not result or not result['cloudinary_folder']:
            return jsonify({'error': 'Dataset not found'}), 404
        
        cloudinary_folder = result['cloudinary_folder']
        
        # Build Cloudinary URL
        # Remove file extension from image name for public_id
        image_name = os.path.splitext(image)[0]
        cloudinary_path = f"{cloudinary_folder}/{person}/{image_name}"
        
        # Generate Cloudinary URL
        url = cloudinary.CloudinaryImage(cloudinary_path).build_url()
        
        # Redirect to Cloudinary URL
        from flask import redirect
        return redirect(url)
        
    except Exception as e:
        print(f"Error fetching image: {e}")
        return jsonify({'error': 'Image not found'}), 404

@bp.route('/status', methods=['GET'])
def dataset_status():
    """Get dataset upload status - MODIFIED for Cloudinary"""
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    project = get_active_project()
    if not project:
        return jsonify({'error': 'No active project'}), 400
    
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT dataset_uploaded, model_trained, cloudinary_folder 
            FROM projects 
            WHERE id = ?
        ''', (project['id'],))
        
        result = cursor.fetchone()
        conn.close()
        
        if not result:
            return jsonify({'error': 'Project not found'}), 404
        
        stats = None
        if result['dataset_uploaded'] and result.get('cloudinary_folder'):
            # Get stats from Cloudinary
            try:
                cloudinary_folder = result['cloudinary_folder']
                resources = cloudinary.api.resources(
                    type="upload",
                    prefix=cloudinary_folder,
                    max_results=500
                )
                
                # Count persons and images
                persons = set()
                total_images = 0
                for resource in resources.get('resources', []):
                    path_parts = resource['public_id'].split('/')
                    if len(path_parts) >= 4:  # rupx/user_id/project_id/person/image
                        persons.add(path_parts[-2])  # person name
                        total_images += 1
                
                stats = {
                    'total_persons': len(persons),
                    'total_images': total_images
                }
            except:
                stats = {'total_persons': 0, 'total_images': 0}
        
        return jsonify({
            'uploaded': bool(result['dataset_uploaded']),
            'trained': bool(result['model_trained']),
            'stats': stats
        }), 200
        
    except Exception as e:
        print(f"Status error: {e}")
        return jsonify({'error': str(e)}), 500

@bp.route('/cleanup', methods=['POST'])
def cleanup_images():
    """
    Manual cleanup endpoint - Delete training images from Cloudinary
    Use this if you want to free storage without waiting for training
    """
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    project = get_active_project()
    if not project:
        return jsonify({'error': 'No active project'}), 400
    
    if not project.get('model_trained'):
        return jsonify({'error': 'Train the model first before cleaning up images'}), 400
    
    cloudinary_folder = project.get('cloudinary_folder')
    if not cloudinary_folder:
        return jsonify({'error': 'No Cloudinary folder found'}), 404
    
    try:
        # Import the delete function from train module
        from api.train import delete_cloudinary_images
        
        success = delete_cloudinary_images(cloudinary_folder)
        
        if success:
            return jsonify({
                'success': True,
                'message': 'Training images deleted from cloud storage'
            }), 200
        else:
            return jsonify({
                'success': False,
                'message': 'Failed to delete some images'
            }), 500
            
    except Exception as e:
        print(f"Cleanup error: {e}")
        return jsonify({'error': str(e)}), 500
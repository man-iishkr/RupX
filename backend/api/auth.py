from flask import Blueprint, request, jsonify, session
from datetime import datetime
import bcrypt
import re
from utils.db_init import get_db
import sqlite3
import os

bp = Blueprint('auth', __name__)

def validate_email(email):
    """Validate email format"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def validate_password(password):
    """Validate password strength (min 8 chars)"""
    return len(password) >= 8

@bp.route('/signup', methods=['POST'])
def signup():
    """User registration"""
    try:
        data = request.get_json()
        email = data.get('email', '').strip().lower()
        password = data.get('password', '')
        
        # Validation
        if not email or not password:
            return jsonify({'error': 'Email and password required'}), 400
        
        if not validate_email(email):
            return jsonify({'error': 'Invalid email format'}), 400
        
        if not validate_password(password):
            return jsonify({'error': 'Password must be at least 8 characters'}), 400
        
        # Hash password
        password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        
        # Insert user
        conn = get_db()
        cursor = conn.cursor()
        
        try:
            cursor.execute(
                'INSERT INTO users (email, password_hash, created_at) VALUES (?, ?, ?)',
                (email, password_hash, datetime.now().isoformat())
            )
            conn.commit()
            user_id = cursor.lastrowid
            
            # Create session
            session.permanent = True
            session['user_id'] = user_id
            session['email'] = email
            
            conn.close()
            
            return jsonify({
                'success': True,
                'user': {
                    'id': user_id,
                    'email': email
                }
            }), 201
            
        except sqlite3.IntegrityError:
            conn.close()
            return jsonify({'error': 'Email already exists'}), 409
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/login', methods=['POST'])
def login():
    """User login"""
    try:
        data = request.get_json()
        email = data.get('email', '').strip().lower()
        password = data.get('password', '')
        
        if not email or not password:
            return jsonify({'error': 'Email and password required'}), 400
        
        conn = get_db()
        cursor = conn.cursor()
        
        # Get user
        cursor.execute('SELECT * FROM users WHERE email = ?', (email,))
        user = cursor.fetchone()
        
        if not user:
            conn.close()
            return jsonify({'error': 'Invalid credentials'}), 401
        
        # Verify password
        if not bcrypt.checkpw(password.encode('utf-8'), user['password_hash'].encode('utf-8')):
            conn.close()
            return jsonify({'error': 'Invalid credentials'}), 401
        
        # Update last login
        cursor.execute(
            'UPDATE users SET last_login = ? WHERE id = ?',
            (datetime.now().isoformat(), user['id'])
        )
        conn.commit()
        conn.close()
        
        # Create session
        session.permanent = True
        session['user_id'] = user['id']
        session['email'] = user['email']
        
        return jsonify({
            'success': True,
            'user': {
                'id': user['id'],
                'email': user['email']
            }
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/logout', methods=['POST'])
def logout():
    """User logout"""
    session.clear()
    return jsonify({'success': True}), 200

@bp.route('/status', methods=['GET'])
def status():
    """Check authentication status"""
    if 'user_id' in session:
        return jsonify({
            'authenticated': True,
            'user': {
                'id': session['user_id'],
                'email': session['email']
            }
        }), 200
    else:
        return jsonify({'authenticated': False}), 200

@bp.route('/projects', methods=['GET'])
def get_projects():
    """Get user's projects"""
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, name, created_at, is_active, dataset_uploaded, 
                   model_trained, attendance_mode
            FROM projects 
            WHERE user_id = ?
            ORDER BY created_at DESC
        ''', (session['user_id'],))
        
        projects = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        return jsonify({'projects': projects}), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/projects/create', methods=['POST'])
def create_project():
    """Create new project"""
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    try:
        data = request.get_json()
        name = data.get('name', '').strip()
        
        if not name:
            return jsonify({'error': 'Project name required'}), 400
        
        if len(name) > 50:
            return jsonify({'error': 'Project name too long'}), 400
        
        conn = get_db()
        cursor = conn.cursor()
        
        # Check project limit (5 max)
        cursor.execute('SELECT COUNT(*) as count FROM projects WHERE user_id = ?', 
                      (session['user_id'],))
        count = cursor.fetchone()['count']
        
        if count >= 5:
            conn.close()
            return jsonify({'error': 'Maximum 5 projects allowed'}), 403
        
        # Deactivate other projects
        cursor.execute('UPDATE projects SET is_active = 0 WHERE user_id = ?',
                      (session['user_id'],))
        
        # Create project
        try:
            cursor.execute('''
                INSERT INTO projects (user_id, name, created_at, is_active) 
                VALUES (?, ?, ?, 1)
            ''', (session['user_id'], name, datetime.now().isoformat()))
            
            conn.commit()
            project_id = cursor.lastrowid
            
            # Create project directory
            import os
            project_dir = f'storage/users/{session["user_id"]}/projects/{project_id}'
            os.makedirs(f'{project_dir}/dataset', exist_ok=True)
            os.makedirs(f'{project_dir}/models', exist_ok=True)
            os.makedirs(f'{project_dir}/attendance', exist_ok=True)
            
            conn.close()
            
            return jsonify({
                'success': True,
                'project': {
                    'id': project_id,
                    'name': name
                }
            }), 201
            
        except sqlite3.IntegrityError:
            conn.close()
            return jsonify({'error': 'Project name already exists'}), 409
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/projects/<int:project_id>/activate', methods=['POST'])
def activate_project(project_id):
    """Set active project"""
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Verify ownership
        cursor.execute('SELECT id FROM projects WHERE id = ? AND user_id = ?',
                      (project_id, session['user_id']))
        
        if not cursor.fetchone():
            conn.close()
            return jsonify({'error': 'Project not found'}), 404
        
        # Deactivate all, then activate this one
        cursor.execute('UPDATE projects SET is_active = 0 WHERE user_id = ?',
                      (session['user_id'],))
        cursor.execute('UPDATE projects SET is_active = 1 WHERE id = ?',
                      (project_id,))
        
        conn.commit()
        conn.close()
        
        return jsonify({'success': True}), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/projects/<int:project_id>', methods=['DELETE'])
def delete_project(project_id):
    """Delete project"""
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Verify ownership
        cursor.execute('SELECT id FROM projects WHERE id = ? AND user_id = ?',
                      (project_id, session['user_id']))
        
        if not cursor.fetchone():
            conn.close()
            return jsonify({'error': 'Project not found'}), 404
        
        # Delete project
        cursor.execute('DELETE FROM projects WHERE id = ?', (project_id,))
        conn.commit()
        conn.close()
        
        # Delete project directory
        import shutil
        project_dir = f'storage/users/{session["user_id"]}/projects/{project_id}'
        if os.path.exists(project_dir):
            shutil.rmtree(project_dir)
        
        return jsonify({'success': True}), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500
from flask import Blueprint, request, jsonify, session
from datetime import datetime
import bcrypt
import re
from utils.db_init import get_db
from utils.email_service import create_otp, verify_otp, send_verification_email, resend_otp
import sqlite3
import os

bp = Blueprint('auth', __name__)

def validate_email(email):
    """Validate email format"""
    # Added the $ at the end to properly close the validation
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None


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
        
        # Check if email is verified
        is_verified = str(user['verified']) == '1' or user['verified'] == 1
        if not is_verified:
            conn.close()
            return jsonify({
                'error': 'Email not verified',
                'needs_verification': True,
                'email': email
            }), 403
        
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
        import traceback
        print("--- LOGIN ERROR TRACEBACK ---")
        traceback.print_exc() # This prints to your VS Code/Terminal console
        print("------------------------------")
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
        attendance_mode = data.get('attendance_mode', 'daily').lower()  # NEW
        
        if not name:
            return jsonify({'error': 'Project name required'}), 400
        
        if len(name) > 50:
            return jsonify({'error': 'Project name too long'}), 400
        
        if attendance_mode not in ['daily', 'sessional']:
            return jsonify({'error': 'Invalid attendance mode'}), 400
        
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
                INSERT INTO projects (user_id, name, created_at, is_active, attendance_mode) 
                VALUES (?, ?, ?, 1, ?)
            ''', (session['user_id'], name, datetime.now().isoformat(), attendance_mode))
            
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
                    'name': name,
                    'attendance_mode': attendance_mode
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

    return re.match(pattern, email) is not None

def validate_password(password):
    """Validate password strength (min 8 chars)"""
    return len(password) >= 8

@bp.route('/signup', methods=['POST'])
def signup():
    """User registration - Step 1: Send OTP"""
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
        
        # Check if email already exists
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT id FROM users WHERE email = ?', (email,))
        if cursor.fetchone():
            conn.close()
            return jsonify({'error': 'Email already exists'}), 409
        conn.close()
        
        # Generate and send OTP
        otp = create_otp(email)
        success = send_verification_email(email, otp)
        
        if not success:
            return jsonify({'error': 'Failed to send verification email. Please check SMTP configuration.'}), 500
        
        # Store password temporarily in session (will be used after verification)
        session['pending_signup'] = {
            'email': email,
            'password': password
        }
        
        return jsonify({
            'success': True,
            'message': 'OTP sent to your email',
            'email': email
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/verify-otp', methods=['POST'])
def verify_otp_endpoint():
    """Verify OTP and complete registration"""
    try:
        data = request.get_json()
        email = data.get('email', '').strip().lower()
        otp = data.get('otp', '').strip()
        
        print(f"[DEBUG] Verify OTP request - Email: {email}, OTP: {otp}")  # Debug log
        
        if not email or not otp:
            return jsonify({
                'success': False,
                'message': 'Email and OTP required'
            }), 400
        
        # Verify OTP
        verified, message = verify_otp(email, otp)
        
        print(f"[DEBUG] OTP verification result - Verified: {verified}, Message: {message}")  # Debug log
        
        if not verified:
            return jsonify({
                'success': False,
                'message': message
            }), 400
        
        conn = get_db()
        cursor = conn.cursor()
        
        # Check if user already exists (unverified)
        cursor.execute('SELECT id, verified FROM users WHERE email = ?', (email,))
        existing_user = cursor.fetchone()
        
        if existing_user:
            print(f"[DEBUG] Existing user found - ID: {existing_user['id']}, Verified: {existing_user['verified']}")
            
            # User exists but not verified - just mark as verified
            if not existing_user['verified']:
                cursor.execute('UPDATE users SET verified = 1 WHERE email = ?', (email,))
                conn.commit()
            
            user_id = existing_user['id']
            
            # Create session
            session.permanent = True
            session['user_id'] = user_id
            session['email'] = email
            
            # Clear pending signup if exists
            session.pop('pending_signup', None)
            
            conn.close()
            
            print(f"[DEBUG] User verified successfully - ID: {user_id}")
            
            return jsonify({
                'success': True,
                'message': 'Email verified successfully',
                'user': {
                    'id': user_id,
                    'email': email
                }
            }), 200
        
        # Get pending signup data (new user)
        pending = session.get('pending_signup')
        
        print(f"[DEBUG] Pending signup data: {pending}")
        
        if not pending:
            conn.close()
            return jsonify({
                'success': False,
                'message': 'No pending signup found. Please sign up first.'
            }), 400
        
        if pending['email'] != email:
            conn.close()
            return jsonify({
                'success': False,
                'message': 'Email mismatch with pending signup'
            }), 400
        
        # Hash password
        password_hash = bcrypt.hashpw(pending['password'].encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        
        # Create user
        try:
            cursor.execute(
                'INSERT INTO users (email, password_hash, created_at, verified) VALUES (?, ?, ?, 1)',
                (email, password_hash, datetime.now().isoformat())
            )
            conn.commit()
            user_id = cursor.lastrowid
            
            print(f"[DEBUG] New user created - ID: {user_id}")
            
            # Create user storage directory
            user_dir = f'storage/users/{user_id}'
            os.makedirs(f'{user_dir}/projects', exist_ok=True)
            
            # Create session
            session.permanent = True
            session['user_id'] = user_id
            session['email'] = email
            
            # Clear pending signup
            session.pop('pending_signup', None)
            
            conn.close()
            
            return jsonify({
                'success': True,
                'message': 'Account created successfully',
                'user': {
                    'id': user_id,
                    'email': email
                }
            }), 201
            
        except sqlite3.IntegrityError as e:
            conn.close()
            print(f"[ERROR] Database error: {e}")
            return jsonify({
                'success': False,
                'message': 'Email already exists'
            }), 409
            
        except Exception as e:
            conn.close()
            print(f"[ERROR] Unexpected error: {e}")
            return jsonify({
                'success': False,
                'message': f'Database error: {str(e)}'
            }), 500
            
    except Exception as e:
        print(f"[ERROR] Exception in verify_otp_endpoint: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': f'Server error: {str(e)}'
        }), 500

@bp.route('/resend-otp', methods=['POST'])
def resend_otp_endpoint():
    """Resend OTP"""
    try:
        data = request.get_json()
        email = data.get('email', '').strip().lower()
        
        if not email:
            return jsonify({'error': 'Email required'}), 400
        
        # Check if there's a pending signup OR if user exists but not verified
        pending = session.get('pending_signup')
        
        if pending and pending['email'] == email:
            # Has pending signup - resend
            success = resend_otp(email)
        else:
            # Check if user exists but not verified
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute('SELECT verified FROM users WHERE email = ?', (email,))
            user = cursor.fetchone()
            conn.close()
            
            if user and not user['verified']:
                # User exists but not verified - create new OTP
                otp = create_otp(email)
                success = send_verification_email(email, otp)
            else:
                return jsonify({'error': 'No pending verification for this email'}), 400
        
        if success:
            return jsonify({'success': True, 'message': 'OTP resent'}), 200
        else:
            return jsonify({'error': 'Failed to resend OTP'}), 500
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500
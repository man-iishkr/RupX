from flask import Flask, request, jsonify, session, send_file
from flask_socketio import SocketIO, emit
from flask_cors import CORS
import os
import secrets
from datetime import datetime, timedelta
from functools import wraps

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', secrets.token_hex(32))
app.config['SESSION_COOKIE_SAMESITE'] = 'None'  # Changed for cross-origin
app.config['SESSION_COOKIE_SECURE'] = True      # Required with SameSite=None
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7)
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB max upload

# CORS Configuration - CRITICAL FIX
CORS(app, 
     supports_credentials=True,
     origins=[
         'http://127.0.0.1:8080',
         'http://localhost:8080',
         'https://rupx-backend.onrender.com',
         'https://rupx.netlify.app'
     ],
     allow_headers=['Content-Type', 'Authorization'],
     expose_headers=['Content-Type'],
     methods=['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'])

# Initialize SocketIO with optimized settings
socketio = SocketIO(
    app, 
    cors_allowed_origins=[
        'http://127.0.0.1:8080', 
        'http://localhost:8080',
        'https://rupx-backend.onrender.com',
        'https://rupx.netlify.app'
    ], 
    async_mode='threading',
    ping_timeout=120,          # Increased timeout
    ping_interval=25,
    max_http_buffer_size=10 * 1024 * 1024  # 10MB buffer
)

# Create storage directories
os.makedirs('storage/users', exist_ok=True)
os.makedirs('database', exist_ok=True)
os.makedirs('storage/models', exist_ok=True)

# Initialize database connection
from utils.db import get_db, init_db, DB_TYPE

# Initialize database on startup
def initialize_database():
    """Initialize database if not already set up"""
    print("\n" + "=" * 60)
    print("Database Initialization")
    print("=" * 60)
    
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Check if users table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
        result = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        # Handle both dict and tuple results
        has_users_table = False
        if result:
            if isinstance(result, dict):
                has_users_table = result.get('name') == 'users'
            else:
                has_users_table = result[0] == 'users'
        
        if not has_users_table:
            print("⚠️  Users table not found. Initializing schema...")
            init_db()
            print("✅ Database initialized")
        else:
            print("✅ Database ready")
            
    except Exception as e:
        print(f"⚠️  Database check failed: {e}")
        print("   Attempting initialization...")
        try:
            init_db()
            print("✅ Database initialized")
        except Exception as init_error:
            print(f"❌ Initialization failed: {init_error}")
            print("\n⚠️  APP WILL START BUT DATABASE MAY NOT WORK")
    
    print("=" * 60 + "\n")

# Call initialization with timeout protection
try:
    initialize_database()
except Exception as e:
    print(f"❌ Critical error during startup: {e}")

# Import API routes
from api import auth, dataset, train, recognize, attendance

# Register blueprints
app.register_blueprint(auth.bp, url_prefix='/api/auth')
app.register_blueprint(dataset.bp, url_prefix='/api/dataset')
app.register_blueprint(train.bp, url_prefix='/api/train')
app.register_blueprint(recognize.bp, url_prefix='/api/recognize')
app.register_blueprint(attendance.bp, url_prefix='/api/attendance')

# Import WebSocket handlers (only if needed)
try:
    from websocket import video_stream
    video_stream.init_socketio(socketio)
except ImportError:
    print("⚠️  WebSocket module not found, skipping video stream")

# Error handlers
@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Endpoint not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    app.logger.error(f"Server Error: {error}")
    return jsonify({'error': 'Internal server error'}), 500

@app.errorhandler(413)
def too_large(error):
    return jsonify({'error': 'File too large. Max 50MB'}), 413

# Health check & Root
@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({
        'status': 'healthy', 
        'timestamp': datetime.now().isoformat(),
        'database': DB_TYPE
    })

@app.route('/', methods=['GET'])
def root():
    return jsonify({
        'name': 'RupX API', 
        'version': '1.0.0', 
        'status': 'running',
        'database': DB_TYPE
    })

# Add OPTIONS handler for CORS preflight
@app.before_request
def handle_preflight():
    if request.method == 'OPTIONS':
        response = jsonify({'status': 'ok'})
        response.headers.add('Access-Control-Allow-Origin', request.headers.get('Origin', '*'))
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
        response.headers.add('Access-Control-Allow-Methods', 'GET,POST,PUT,DELETE,OPTIONS')
        response.headers.add('Access-Control-Allow-Credentials', 'true')
        return response, 200

if __name__ == '__main__':
    print("=" * 60)
    print("RupX Backend Server")
    print("=" * 60)
    print(f"Database: {DB_TYPE.upper()}")
    print("Server: http://0.0.0.0:5000")
    print("WebSocket: ws://0.0.0.0:5000/socket.io")
    print("=" * 60)
    
    # Get port from environment
    port = int(os.environ.get('PORT', 5000))
    
    # Run with SocketIO
    socketio.run(
        app, 
        host='0.0.0.0',
        port=port, 
        debug=False,  # NEVER True in production
        allow_unsafe_werkzeug=True
    )
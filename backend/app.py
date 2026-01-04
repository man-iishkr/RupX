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
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7)
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB max upload

# Enable CORS
CORS(app, 
     supports_credentials=True, 
     origins=[
         'http://127.0.0.1:8080', 
         'http://localhost:8080',
         'https://rupx-backend.onrender.com',
         'https://rupx.netlify.app'
     ])

# Initialize SocketIO
socketio = SocketIO(
    app, 
    cors_allowed_origins=[
        'http://127.0.0.1:8080', 
        'http://localhost:8080',
        'https://rupx-backend.onrender.com',
        'https://rupx.netlify.app'
    ], 
    async_mode='threading',
    ping_timeout=60, 
    ping_interval=25
)

# Create storage directories
os.makedirs('storage/users', exist_ok=True)
os.makedirs('database', exist_ok=True)
os.makedirs('storage/models', exist_ok=True)

# Initialize database connection based on environment
if os.getenv('TURSO_DATABASE_URL'):
    from utils.db_turso import init_db, get_db
    print("📊 Using Turso (Cloud SQLite)")
    DB_TYPE = 'turso'
else:
    from utils.db_init import init_db, get_db
    print("📊 Using Local SQLite")
    DB_TYPE = 'local'

# Initialize database on startup
def initialize_database():
    """Initialize database if not already set up"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Check if users table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
        result = cursor.fetchone()
        
        if not result:
            print("⚠️  Database tables not found. Initializing...")
            cursor.close()
            conn.close()
            init_db()
            print("✅ Database initialized successfully")
        else:
            print("✅ Database ready")
            cursor.close()
            conn.close()
            
    except Exception as e:
        print(f"⚠️  Database error: {e}")
        print("   Attempting to initialize database...")
        try:
            init_db()
            print("✅ Database initialized successfully")
        except Exception as init_error:
            print(f"❌ Failed to initialize database: {init_error}")
            import traceback
            traceback.print_exc()

# Call initialization
initialize_database()

# Import API routes
from api import auth, dataset, train, recognize, attendance

# Register blueprints
app.register_blueprint(auth.bp, url_prefix='/api/auth')
app.register_blueprint(dataset.bp, url_prefix='/api/dataset')
app.register_blueprint(train.bp, url_prefix='/api/train')
app.register_blueprint(recognize.bp, url_prefix='/api/recognize')
app.register_blueprint(attendance.bp, url_prefix='/api/attendance')

# Import WebSocket handlers
from websocket import video_stream

# Initialize video streaming
video_stream.init_socketio(socketio)

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

if __name__ == '__main__':
    print("=" * 60)
    print("RupX Backend Server")
    print("=" * 60)
    print(f"Database: {DB_TYPE.upper()}")
    print("Server: http://127.0.0.1:5000")
    print("WebSocket: ws://127.0.0.1:5000/socket.io")
    print("=" * 60)
    
    # Get port from environment or default to 5000
    port = int(os.environ.get('PORT', 5000))
    
    # Run with SocketIO
    socketio.run(
        app, 
        host='0.0.0.0',  # Changed to 0.0.0.0 for deployment
        port=port, 
        debug=os.getenv('FLASK_ENV') == 'development',
        allow_unsafe_werkzeug=True
    )
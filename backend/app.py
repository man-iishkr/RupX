from flask import Flask, request, jsonify, session, send_file
from flask_socketio import SocketIO, emit
from flask_cors import CORS
import os
import secrets
from datetime import datetime, timedelta
from functools import wraps

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = secrets.token_hex(32)
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7)
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB max upload

# Enable CORS - Ensure your frontend port (8080) is authorized
CORS(app, supports_credentials=True, origins=['http://127.0.0.1:8080', 'http://localhost:8080'])

# Initialize SocketIO
# CHANGED: async_mode set to None to allow eventlet to take over (more stable for workers)
socketio = SocketIO(app, 
                    cors_allowed_origins=['http://127.0.0.1:8080', 'http://localhost:8080'], 
                    async_mode='threading', # Force standard threading
                    ping_timeout=60, 
                    ping_interval=25)

# Create storage directories
os.makedirs('storage/users', exist_ok=True)
os.makedirs('database', exist_ok=True)
# Ensure the models directory exists for recognition
os.makedirs('storage/models', exist_ok=True)

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

# Initialize video streaming (passing the socketio instance)
video_stream.init_socketio(socketio)

# Error handlers
@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Endpoint not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    # Added logging here to help debug the "float and dict" error if it persists
    app.logger.error(f"Server Error: {error}")
    return jsonify({'error': 'Internal server error'}), 500

@app.errorhandler(413)
def too_large(error):
    return jsonify({'error': 'File too large. Max 50MB'}), 413

# Health check & Root
@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'healthy', 'timestamp': datetime.now().isoformat()})

@app.route('/', methods=['GET'])
def root():
    return jsonify({'name': 'RupX API', 'version': '1.0.0', 'status': 'running'})

if __name__ == '__main__':
    print("=" * 60)
    print("RupX Backend Server (NumPy 2.x Optimized)")
    print("=" * 60)
    print("Server: http://127.0.0.1:5000")
    print("WebSocket: ws://127.0.0.1:5000/socket.io")
    print("=" * 60)
    
    # Run with SocketIO - allow_unsafe_werkzeug=True is needed for Flask 3.x/Werkzeug 3.x
    port = int(os.environ.get('PORT', 5000))
    socketio.run(app, host='127.0.0.1', port=port, debug=False, allow_unsafe_werkzeug=True)
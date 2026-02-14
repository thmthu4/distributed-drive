from flask import Flask, request, send_from_directory, jsonify
import os
import sys
import jwt
import functools

# Configuration
SECRET_KEY = 'supersecretkey'  # Must match Master Node

# Get port from command line args or default to 5001
port = int(sys.argv[1]) if len(sys.argv) > 1 else 5001
DATA_DIR = f'data_{port}'

app = Flask(__name__)

if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

def require_token(action):
    def decorator(f):
        @functools.wraps(f)
        def wrapper(*args, **kwargs):
            token = request.args.get('token') or request.form.get('token')
            if not token:
                return jsonify({'error': 'Missing token'}), 401
            try:
                payload = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
                if payload.get('action') != action:
                    return jsonify({'error': 'Invalid token action'}), 403
            except jwt.ExpiredSignatureError:
                return jsonify({'error': 'Token expired'}), 401
            except jwt.InvalidTokenError:
                return jsonify({'error': 'Invalid token'}), 401
            return f(*args, **kwargs)
        return wrapper
    return decorator

@app.route('/')
def status():
    return jsonify({'status': 'active', 'port': port, 'files': len(os.listdir(DATA_DIR))})

@app.route('/upload', methods=['POST'])
@require_token('upload')
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    file = request.files['file']
    filename = request.form.get('filename') # Master tells us what to name it (chunk id)
    
    if not filename:
        return jsonify({'error': 'Filename (chunk_id) required'}), 400
    
    # Save file
    file.save(os.path.join(DATA_DIR, filename))
    return jsonify({'status': 'uploaded', 'filename': filename}), 200

@app.route('/download/<filename>', methods=['GET'])
@require_token('download')
def download_file(filename):
    return send_from_directory(DATA_DIR, filename)

def register_self():
    master_url = os.environ.get('MASTER_URL')
    public_host = os.environ.get('PUBLIC_HOST')
    
    if not master_url or not public_host:
        return
        
    import time
    import requests
    
    time.sleep(5) # Wait for server to start
    
    # Address accessible by User Browser
    public_address = f"http://{public_host}:{port}"
    
    payload = {
        'name': f"Node_{port}",
        'address': public_address
    }
    
    print(f"Attempting to register with Master at {master_url}...")
    for i in range(10):
        try:
            requests.post(f"{master_url}/api/register_node", json=payload)
            print(f"Successfully registered as {public_address}")
            break
        except Exception as e:
            print(f"Registration failed (attempt {i+1}): {e}")
            time.sleep(5)

if __name__ == '__main__':
    # Start registration in background if env vars exist
    if os.environ.get('MASTER_URL'):
        import threading
        threading.Thread(target=register_self, daemon=True).start()

    print(f"Starting Storage Node on port {port}...")
    app.run(host='0.0.0.0', port=port, debug=True)

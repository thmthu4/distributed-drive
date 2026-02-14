from flask import Flask, render_template, request, redirect, url_for, session, jsonify, Response, stream_with_context
import sqlite3
import os
import requests
import jwt
import datetime
import uuid
from models import get_db_connection, init_db

app = Flask(__name__)
app.secret_key = 'supersecretkey'  # Used for session and JWT

# Initialize DB on startup
if not os.path.exists('metadata.db'):
    init_db()

def create_default_admin():
    conn = get_db_connection()
    try:
        # Check if admin exists
        admin = conn.execute("SELECT * FROM users WHERE username = 'admin'").fetchone()
        if not admin:
            conn.execute("INSERT INTO users (username, password, is_admin) VALUES (?, ?, ?)",
                         ('admin', 'admin123', 1))
            conn.commit()
            print("Default admin account created: admin / admin123")
    except Exception as e:
        print(f"Error creating admin: {e}")
    finally:
        conn.close()

create_default_admin()

def generate_token(action, expires_in=300):
    payload = {
        'action': action,
        'exp': datetime.datetime.utcnow() + datetime.timedelta(seconds=expires_in)
    }
    return jwt.encode(payload, app.secret_key, algorithm='HS256')

@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

# --- Auth Routes ---
@app.route('/auth/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        conn = get_db_connection()
        try:
            conn.execute('INSERT INTO users (username, password) VALUES (?, ?)',
                         (username, password))
            conn.commit()
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            return "Username already exists"
        finally:
            conn.close()
    return render_template('register.html')

@app.route('/auth/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
        conn.close()
        
        if user and user['password'] == password:
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['is_admin'] = user['is_admin']
            return redirect(url_for('dashboard'))
        else:
            return "Invalid credentials"
    return render_template('login.html')

@app.route('/auth/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# --- Dashboard ---
@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    files = conn.execute('SELECT * FROM files WHERE user_id = ?', (session['user_id'],)).fetchall()
    nodes = conn.execute('SELECT * FROM storage_nodes').fetchall()
    conn.close()
    
    return render_template('dashboard.html', files=files, nodes=nodes, user=session)

# --- Admin ---
@app.route('/admin')
def admin():
    if 'user_id' not in session or not session.get('is_admin'):
        return "Access Denied"
    
    conn = get_db_connection()
    users = conn.execute('SELECT * FROM users').fetchall()
    nodes = conn.execute('SELECT * FROM storage_nodes').fetchall()
    
    # Get Files with their chunks
    files_db = conn.execute('SELECT * FROM files').fetchall()
    files_data = []
    
    for f in files_db:
        # Get chunks for this file
        chunks = conn.execute('''
            SELECT c.sequence, c.chunk_id, s.name as node_name, s.address
            FROM chunks c
            JOIN storage_nodes s ON c.storage_node_id = s.id
            WHERE c.file_id = ?
            ORDER BY c.sequence
        ''', (f['id'],)).fetchall()
        
        files_data.append({
            'metadata': f,
            'chunks': chunks
        })
        
    conn.close()
    
    return render_template('admin.html', users=users, nodes=nodes, files=files_data)

# --- File Operations (Chunking) ---
CHUNK_SIZE = 1 * 1024 * 1024 # 1 MB

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    if 'file' not in request.files:
        return "No file part"
    
    file = request.files['file']
    if file.filename == '':
        return "No selected file"

    conn = get_db_connection()
    nodes = conn.execute("SELECT * FROM storage_nodes WHERE status='active'").fetchall()
    
    if not nodes:
        conn.close()
        return "No active storage nodes available"

    # Create File Record
    cursor = conn.execute('INSERT INTO files (filename, user_id, size) VALUES (?, ?, ?)',
                         (file.filename, session['user_id'], 0))
    file_id = cursor.lastrowid
    conn.commit() # Commit immediately to release lock
    
    total_size = 0
    sequence = 0
    
    try:
        while True:
            chunk_data = file.read(CHUNK_SIZE)
            if not chunk_data:
                break
            
            chunk_size = len(chunk_data)
            total_size += chunk_size
            
            # Select Node (Round Robin)
            node = nodes[sequence % len(nodes)]
            
            # Generate Chunk ID
            chunk_id = f"{file_id}_{sequence}_{uuid.uuid4().hex}"
            
            # Generate Token
            token = generate_token('upload')
            
            # Send to Node
            files = {'file': (chunk_id, chunk_data, 'application/octet-stream')}
            data = {'filename': chunk_id, 'token': token}
            
            # Release DB connection during network call? 
            # Ideally yes, but we are inside a route. 
            # Valid because we committed above.
            
            response = requests.post(f"{node['address']}/upload", files=files, data=data)
            
            if response.status_code != 200:
                raise Exception(f"Failed to upload chunk {sequence} to {node['name']}: {response.text}")
            
            # Record Chunk
            conn.execute('INSERT INTO chunks (file_id, sequence, storage_node_id, chunk_id) VALUES (?, ?, ?, ?)',
                         (file_id, sequence, node['id'], chunk_id))
            conn.commit() # Commit each chunk
            
            sequence += 1
            
        # Update File Size
        conn.execute('UPDATE files SET size = ? WHERE id = ?', (total_size, file_id))
        conn.commit()
        return redirect(url_for('dashboard'))
        
    except Exception as e:
        conn.rollback()
        return f"Upload failed: {str(e)}"
    finally:
        conn.close()

@app.route('/download_link/<int:file_id>')
def download_file_route(file_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    # Stream the file back to consumer
    return Response(stream_with_context(generate_file_stream(file_id)), 
                   headers={'Content-Disposition': f'attachment; filename=download_{file_id}'})

def generate_file_stream(file_id):
    conn = get_db_connection()
    chunks = conn.execute('''
        SELECT c.chunk_id, s.address 
        FROM chunks c 
        JOIN storage_nodes s ON c.storage_node_id = s.id 
        WHERE c.file_id = ? 
        ORDER BY c.sequence
    ''', (file_id,)).fetchall()
    conn.close()
    
    token = generate_token('download')
    
    for chunk in chunks:
        # Fetch chunk from storage node
        url = f"{chunk['address']}/download/{chunk['chunk_id']}?token={token}"
        with requests.get(url, stream=True) as r:
            for data in r.iter_content(chunk_size=4096):
                yield data

@app.route('/share/<int:file_id>')
def share_file(file_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    public_link = url_for('shared_file_view', file_id=file_id, _external=True)
    return render_template('share_view.html', link=public_link, file_id=file_id)

@app.route('/shared/<int:file_id>')
def shared_file_view(file_id):
    conn = get_db_connection()
    file = conn.execute('SELECT * FROM files WHERE id = ?', (file_id,)).fetchone()
    conn.close()
    if not file:
        return "File not found or link expired."
    return render_template('public_download.html', file=file)

@app.route('/public_download/<int:file_id>')
def public_download_action(file_id):
    return Response(stream_with_context(generate_file_stream(file_id)), 
                   headers={'Content-Disposition': f'attachment; filename=shared_download_{file_id}'})

# --- API for Storage Nodes ---
@app.route('/api/register_node', methods=['POST'])
def register_node():
    data = request.json
    name = data.get('name')
    address = data.get('address')
    
    conn = get_db_connection()
    try:
        conn.execute('INSERT INTO storage_nodes (name, address) VALUES (?, ?) ON CONFLICT(address) DO UPDATE SET last_heartbeat=CURRENT_TIMESTAMP', (name, address))
        conn.commit()
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()
    return jsonify({'status': 'registered'})

if __name__ == '__main__':
    # Listen on all interfaces for Docker
    app.run(host='0.0.0.0', port=5000, debug=True)

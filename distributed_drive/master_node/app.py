from flask import Flask, render_template, request, redirect, url_for, session, jsonify, Response, stream_with_context
import sqlite3
import os
import requests
import jwt
import datetime
import uuid
import hashlib
import mimetypes
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
    print(f"DEBUG: Starting upload for {file.filename} (file_id: {file_id})")
    
    try:
        while True:
            chunk_data = file.read(CHUNK_SIZE)
            chunk_len = len(chunk_data)
            print(f"DEBUG: Read chunk {sequence}: {chunk_len} bytes")
            if not chunk_data:
                print(f"DEBUG: End of file reached for sequence {sequence}")
                break
            
            chunk_hash = hashlib.sha256(chunk_data).hexdigest()
            chunk_size = len(chunk_data)
            total_size += chunk_size
            
            # Select up to 2 Nodes for Replication
            selected_nodes = []
            for i in range(min(2, len(nodes))):
                node = nodes[(sequence + i) % len(nodes)]
                selected_nodes.append(node)
            
            # Generate Chunk ID
            chunk_id = f"{file_id}_{sequence}_{uuid.uuid4().hex}"
            
            # Generate Token
            token = generate_token('upload')
            
            successful_replicas = 0
            last_error = None
            # Send to Nodes
            for node in selected_nodes:
                files = {'file': (chunk_id, chunk_data, 'application/octet-stream')}
                data = {'filename': chunk_id, 'token': token}
                
                try:
                    response = requests.post(f"{node['address']}/upload", files=files, data=data)
                    response.raise_for_status()
                    
                    # Record Chunk
                    conn.execute('INSERT INTO chunks (file_id, sequence, storage_node_id, chunk_id, checksum) VALUES (?, ?, ?, ?, ?)',
                                 (file_id, sequence, node['id'], chunk_id, chunk_hash))
                    successful_replicas += 1
                except Exception as e:
                    print(f"Warning: Failed to upload replica to {node['name']}: {e}")
                    last_error = str(e)
            
            if successful_replicas == 0:
                print(f"ERROR: Failed to upload chunk {sequence} to ANY node. Last error: {last_error}")
                raise Exception(f"Failed to upload chunk {sequence} to ANY node. Last error: {last_error}")
                
            print(f"DEBUG: Successfully pushed chunk {sequence} to {successful_replicas} nodes.")
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
    
    conn = get_db_connection()
    file_info = conn.execute('SELECT * FROM files WHERE id = ?', (file_id,)).fetchone()
    conn.close()
    
    if not file_info:
        return "File not found", 404
        
    mimetype = mimetypes.guess_type(file_info['filename'])[0] or 'application/octet-stream'
    
    return Response(stream_with_context(generate_file_stream(file_id)), 
                   headers={
                       'Content-Disposition': f'attachment; filename="{file_info["filename"]}"',
                       'Content-Type': mimetype
                   })

def generate_file_stream(file_id):
    conn = get_db_connection()
    chunks = conn.execute('''
        SELECT c.chunk_id, s.address, c.checksum, c.sequence 
        FROM chunks c 
        JOIN storage_nodes s ON c.storage_node_id = s.id 
        WHERE c.file_id = ? 
        ORDER BY c.sequence
    ''', (file_id,)).fetchall()
    conn.close()
    
    # Group replicas by sequence
    from collections import defaultdict
    replicas_by_seq = defaultdict(list)
    for row in chunks:
        replicas_by_seq[row['sequence']].append(row)
    
    token = generate_token('download')
    
    for seq in sorted(replicas_by_seq.keys()):
        replicas = replicas_by_seq[seq]
        success = False
        print(f"DEBUG: Starting download for chunk seq {seq} (Replicas: {len(replicas)})")
        
        for chunk in replicas:
            url = f"{chunk['address']}/download/{chunk['chunk_id']}?token={token}"
            expected_hash = chunk['checksum']
            chunk_buffer = bytearray()
            
            try:
                with requests.get(url, stream=True, timeout=5) as r:
                    r.raise_for_status()
                    for data in r.iter_content(chunk_size=4096):
                        if expected_hash:
                            chunk_buffer.extend(data)
                        else:
                            yield data
                            
                if expected_hash:
                    actual_hash = hashlib.sha256(chunk_buffer).hexdigest()
                    if actual_hash != expected_hash:
                        print(f"ERROR: Integrity check failed for chunk {chunk['chunk_id']}")
                        raise Exception(f"Integrity check failed for {chunk['chunk_id']}")
                    print(f"DEBUG: Successfully verified and yielding {len(chunk_buffer)} bytes for sequence {seq}")
                    yield bytes(chunk_buffer)
                    
                success = True
                break # Mvoe to next sequence if successful
                
            except Exception as e:
                print(f"Warning: Failed to fetch chunk {seq} replica from {chunk['address']}: {e}")
                
        if not success:
            raise Exception(f"Download failed: Exhausted all replicas for chunk {seq}")

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
    conn = get_db_connection()
    file_info = conn.execute('SELECT * FROM files WHERE id = ?', (file_id,)).fetchone()
    conn.close()
    
    if not file_info:
        return "File not found", 404
        
    mimetype = mimetypes.guess_type(file_info['filename'])[0] or 'application/octet-stream'
        
    return Response(stream_with_context(generate_file_stream(file_id)), 
                   headers={
                       'Content-Disposition': f'attachment; filename="{file_info["filename"]}"',
                       'Content-Type': mimetype
                   })

@app.route('/delete_file/<int:file_id>', methods=['POST'])
def delete_file(file_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()
    
    # 1. Check ownership
    file = conn.execute('SELECT * FROM files WHERE id = ?', (file_id,)).fetchone()
    if not file:
        conn.close()
        return "File not found"
        
    if file['user_id'] != session['user_id'] and not session.get('is_admin'):
        conn.close()
        return "Permission denied"

    # 2. Get Chunks
    chunks = conn.execute('''
        SELECT c.chunk_id, s.address 
        FROM chunks c 
        JOIN storage_nodes s ON c.storage_node_id = s.id 
        WHERE c.file_id = ?
    ''', (file_id,)).fetchall()
    
    # 3. Delete from Storage Nodes
    token = generate_token('delete')
    errors = []
    
    for chunk in chunks:
        try:
            requests.delete(f"{chunk['address']}/delete/{chunk['chunk_id']}?token={token}")
        except Exception as e:
            errors.append(str(e))
            # Continue deleting others even if one fails
    
    # 4. Delete Metadata
    conn.execute('DELETE FROM chunks WHERE file_id = ?', (file_id,))
    conn.execute('DELETE FROM files WHERE id = ?', (file_id,))
    conn.commit()
    conn.close()
    
    if errors:
        print(f"Warnings during delete: {errors}")
        
    return redirect(request.referrer or url_for('dashboard'))

# --- API for Storage Nodes ---
@app.route('/api/register_node', methods=['POST'])
def register_node():
    data = request.json
    name = data.get('name')
    address = data.get('address')
    node_key = data.get('node_key')
    
    expected_key = os.environ.get('NODE_REGISTRATION_KEY', 'default_cluster_secret')
    if node_key != expected_key:
        return jsonify({'error': 'Unauthorized node'}), 403
        
    if not name or not address:
        return jsonify({'error': 'Missing data'}), 400
        
    conn = get_db_connection()
    try:
        conn.execute('INSERT INTO storage_nodes (name, address) VALUES (?, ?) ON CONFLICT(address) DO UPDATE SET last_heartbeat=CURRENT_TIMESTAMP', (name, address))
        conn.commit()
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()
    return jsonify({'status': 'registered'})

@app.route('/api/nodes', methods=['GET'])
def get_nodes():
    conn = get_db_connection()
    try:
        nodes = conn.execute('SELECT name, address, status, last_heartbeat FROM storage_nodes').fetchall()
        # Convert sqlite3.Row to dict
        nodes_list = [dict(node) for node in nodes]
        return jsonify({'nodes': nodes_list})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()

if __name__ == '__main__':
    # Listen on all interfaces for Docker
    app.run(host='0.0.0.0', port=5000, debug=True)

import requests
import time
import os
import hashlib
import sys

BASE_URL = 'http://localhost:5000'
STORAGE_NODE_1 = 'http://localhost:5001'

def generate_large_file(filename, size_mb):
    with open(filename, 'wb') as f:
        f.write(os.urandom(int(size_mb * 1024 * 1024)))

def get_file_hash(filename):
    hasher = hashlib.md5()
    with open(filename, 'rb') as f:
        buf = f.read()
        hasher.update(buf)
    return hasher.hexdigest()

def run_test():
    session = requests.Session()
    
    print("--- Setup ---")
    filename = 'large_test.bin'
    if not os.path.exists(filename):
        print("Generating 1.5MB file...")
        generate_large_file(filename, 1.5)
    original_hash = get_file_hash(filename)
    
    # 1. Register/Login
    print("\nTest 1: User Login/Register...")
    try:
        session.post(f'{BASE_URL}/auth/register', data={'username': 'chunkuser', 'password': 'password'})
    except:
        pass
    res = session.post(f'{BASE_URL}/auth/login', data={'username': 'chunkuser', 'password': 'password'})
    if 'Dashboard' in res.text:
        print("PASS: Login successful")
    else:
        print("FAIL: Login failed")
        return

    # 2. Upload Large File
    print("\nTest 2: Uploading 1.5MB file (Should be 2 chunks)...")
    with open(filename, 'rb') as f:
        files = {'file': (filename, f, 'application/octet-stream')}
        res = session.post(f'{BASE_URL}/upload', files=files)
    
    if len(res.history) > 0 and 'redirected' in res.history[0].text.lower() or 'Dashboard' in res.text:
         print("PASS: Upload successful (Master accepted it)")
    else:
         print(f"FAIL: Upload failed. {res.status_code}")
         print(f"Response: {res.text}")

    # 3. Download and Compare
    # ID should be 1 if DB was reset
    print("\nTest 3: Downloading file and comparing hash...")
    res = session.get(f'{BASE_URL}/download_link/1', stream=True)
    if res.status_code == 200:
        downloaded_filename = 'downloaded_large.bin'
        with open(downloaded_filename, 'wb') as f:
            for chunk in res.iter_content(chunk_size=8192):
                f.write(chunk)
        
        down_hash = get_file_hash(downloaded_filename)
        if down_hash == original_hash:
            print(f"PASS: Hashes match ({down_hash})")
        else:
            print(f"FAIL: Hashes mismatch! Orig: {original_hash}, Down: {down_hash}")
    else:
        print(f"FAIL: Download request failed. {res.status_code}")

    # 4. Security Check
    print("\nTest 4: Attempting Direct Storage Access (No Token)...")
    # We need a valid chunk name. It's hard to guess. 
    # But even with invalid filename, we should get 401 Unauthorized for missing token first?
    # Actually my code checks token BEFORE looking for file.
    
    res = requests.get(f'{STORAGE_NODE_1}/download/any_chunk_id')
    if res.status_code == 401:
        print("PASS: Direct access denied (401 Missing Token)")
    else:
        print(f"FAIL: Expected 401, got {res.status_code}")

    print("\nTest 5: Attempting Direct Storage Access (Bad Token)...")
    res = requests.get(f'{STORAGE_NODE_1}/download/any_chunk_id?token=bg.fake.token')
    if res.status_code == 401:  # Should be 401 for invalid token
        print("PASS: Bad token denied (401)")
    else:
        print(f"FAIL: Expected 401, got {res.status_code}")

if __name__ == '__main__':
    try:
        run_test()
    except Exception as e:
        print(f"Test failed: {e}")

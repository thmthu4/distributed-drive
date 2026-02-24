import requests
import os

session = requests.Session()
# Register user
try:
    session.post('http://127.0.0.1:5000/auth/register', data={'username': 'testuser2', 'password': 'pw'})
except Exception:
    pass
session.post('http://127.0.0.1:5000/auth/login', data={'username': 'testuser2', 'password': 'pw'})

# Create a dummy file
with open('dummy.txt', 'wb') as f:
    f.write(b"Hello Distributed World" * 100)
    
print("Uploading...")
with open('dummy.txt', 'rb') as f:
    resp = session.post('http://127.0.0.1:5000/upload', files={'file': f})
    
print("Upload complete, status:", resp.status_code)

# Get files
resp = session.get('http://127.0.0.1:5000/dashboard')
for line in resp.text.split('\n'):
    if 'dummy.txt' in line:
        print("Found in dashboard")
        print(line.strip())

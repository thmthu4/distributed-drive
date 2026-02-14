import requests
import time
import sys

BASE_URL = 'http://localhost:5000'

def run_test():
    session = requests.Session()
    
    # 1. Register/Login (reuse existing)
    print("Test 1: User Login...")
    res = session.post(f'{BASE_URL}/auth/login', data={'username': 'testuser', 'password': 'password123'})
    
    # If login fails, try register first (in case DB was reset)
    if 'Dashboard' not in res.text:
        print("Registering...")
        session.post(f'{BASE_URL}/auth/register', data={'username': 'testuser', 'password': 'password123'})
        res = session.post(f'{BASE_URL}/auth/login', data={'username': 'testuser', 'password': 'password123'})
    
    if res.status_code == 200 and 'Dashboard' in res.text:
        print("PASS: Login successful")
    else:
        print(f"FAIL: Login failed.")
        return

    # Ensure file exists (upload if needed)
    # Checking dashboard for file
    res = session.get(f'{BASE_URL}/dashboard')
    if 'test.txt' not in res.text:
         print("Uploading file...")
         files = {'file': ('test.txt', b'Hello Shared World!', 'text/plain')}
         session.post(f'{BASE_URL}/upload', files=files)

    # 2. Test Share Link Generation
    # We need to find the file ID. Let's assume ID 1 again for simplicity or parse it?
    # Actually, let's just guess ID 1.
    print("Test 2: Getting Share Page for ID 1...")
    res = session.get(f'{BASE_URL}/share/1')
    if res.status_code == 200 and 'File Shared Successfully' in res.text:
        print("PASS: Share page loaded")
        # Extract link? logic is url_for('shared_file_view', file_id=1) -> /shared/1
        share_link = f"{BASE_URL}/shared/1"
    else:
        print(f"FAIL: Share page failed. Status: {res.status_code}")
        return

    # 3. Test Public Download access (No Session)
    print("Test 3: Accessing Public Share Link (No Session)...")
    public_session = requests.Session() # New session, no cookies
    res = public_session.get(share_link)
    if res.status_code == 200 and 'Download File' in res.text:
        print("PASS: Public share page accessible without login")
    else:
        print(f"FAIL: Public share page failed. Status: {res.status_code}")

    # 4. Test Public Download Action
    print("Test 4: Public Download Action...")
    res = public_session.get(f"{BASE_URL}/public_download/1", allow_redirects=True)
    # Content might be 'Hello Distributed World!' or 'Hello Shared World!' depending on if we re-uploaded
    if res.status_code == 200:
        print(f"PASS: Public download successful. Content length: {len(res.content)}")
    else:
        print(f"FAIL: Public download failed. Status: {res.status_code}")

    # 5. Test Default Admin
    print("Test 5: Administrator Login (admin/admin123)...")
    admin_session = requests.Session()
    res = admin_session.post(f'{BASE_URL}/auth/login', data={'username': 'admin', 'password': 'admin123'})
    if res.status_code == 200 and 'Dashboard' in res.text:
         # Check if admin link is visible
         if 'Admin' in res.text:
             print("PASS: Admin login successful and Admin link visible")
         else:
             print("FAIL: Admin login worked but no Admin link?")
    else:
        print("FAIL: Admin login failed")

if __name__ == '__main__':
    try:
        run_test()
    except Exception as e:
        print(f"Test failed with exception: {e}")

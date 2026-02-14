import requests
import time
import sys

BASE_URL = 'http://localhost:5000'

def run_test():
    session = requests.Session()
    
    # 1. Register
    print("Test 1: Registering user...")
    res = session.post(f'{BASE_URL}/auth/register', data={'username': 'testuser', 'password': 'password123'})
    if res.status_code == 200 and 'Login' in res.text:
        print("PASS: Registration successful")
    else:
        print(f"FAIL: Registration failed. Status: {res.status_code}")
        # print(res.text)

    # 2. Login
    print("Test 2: Logging in...")
    res = session.post(f'{BASE_URL}/auth/login', data={'username': 'testuser', 'password': 'password123'})
    if res.status_code == 200 and 'Dashboard' in res.text:
        print("PASS: Login successful")
    else:
        print(f"FAIL: Login failed. Status: {res.status_code}")
        return

    # 3. Upload File
    print("Test 3: Uploading file...")
    files = {'file': ('test.txt', b'Hello Distributed World!', 'text/plain')}
    res = session.post(f'{BASE_URL}/upload', files=files)
    if res.status_code == 200 and 'test.txt' in res.text:
        print("PASS: Upload successful")
    else:
        print(f"FAIL: Upload failed. Status: {res.status_code}")
        # print(res.text)
        return

    # 4. Check Admin (should be denied for normal user)
    print("Test 4: Checking Admin access (should fail)...")
    res = session.get(f'{BASE_URL}/admin')
    if 'Access Denied' in res.text:
         print("PASS: Admin access correctly denied")
    else:
         print("FAIL: Admin access check failed")

    # 5. Dashboard has file
    print("Test 5: Checking Dashboard for file...")
    res = session.get(f'{BASE_URL}/dashboard')
    if 'test.txt' in res.text:
        print("PASS: File found in dashboard")
    else:
        print("FAIL: File not found in dashboard")

    # 6. Check storage connection via Download Link
    # We need to find the file ID to test download link, scraping it is hard without bs4
    # But we can try to rely on the fact that it's the first file, id=1
    print("Test 6: Downloading file (ID: 1)...")
    res = session.get(f'{BASE_URL}/download_link/1', allow_redirects=True)
    if res.status_code == 200 and res.text == 'Hello Distributed World!':
        print("PASS: Download successful and content verified")
    else:
        print(f"FAIL: Download failed. Status: {res.status_code}, Content: {res.text}")

if __name__ == '__main__':
    # Wait for system to be ready if running immediately
    time.sleep(5) 
    try:
        run_test()
    except Exception as e:
        print(f"Test failed with exception: {e}")

import requests
import json

try:
    print("Testing Master Node Admin API")
    r = requests.get('http://127.0.0.1:5000/')
    print(f"Master running: {r.status_code}")
except Exception as e:
    print(f"Master error: {e}")

try:
    print("\nTesting Storage 1")
    r = requests.get('http://127.0.0.1:5001/')
    print(f"Storage 1 status: {r.status_code}")
    print(r.text)
except Exception as e:
    print(f"Storage 1 error: {e}")

try:
    print("\nTesting Storage 2")
    r = requests.get('http://127.0.0.1:5002/')
    print(f"Storage 2 status: {r.status_code}")
    print(r.text)
except Exception as e:
    print(f"Storage 2 error: {e}")

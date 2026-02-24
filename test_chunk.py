import hashlib
import requests
from io import BytesIO

# Dummy data
data = b'test'*1000
expected_hash = hashlib.sha256(data).hexdigest()

print("Expected Hash:", expected_hash)
# We can't hit the flask app easily without running it, but we know requests.post logic:
files = {'file': ('chunk_1', data, 'application/octet-stream')}
print("Files tuple looks ok")

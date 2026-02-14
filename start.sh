#!/bin/bash

echo "=== Auto-Detecting Public IP ==="

# Try to get IP from AWS Service
PUBLIC_IP=$(curl -s http://checkip.amazonaws.com)

if [ -z "$PUBLIC_IP" ]; then
    echo "Error: Could not detect Public IP."
    echo "Usage: sudo ./start.sh"
    exit 1
fi

echo "Detected Public IP: $PUBLIC_IP"

# Export it so docker-compose sees it
export PUBLIC_HOST=$PUBLIC_IP

# Stop any old containers to be safe (and remove volumes if you want a fresh start, but usually we keep data)
# echo "Stopping old containers..."
# sudo -E docker-compose down

echo "=== Starting Distributed Drive ==="
# -E is crucial: it passes the PUBLIC_HOST variable through sudo
sudo -E docker-compose up -d --build

echo ""
echo "✅ System Started!"
echo "👉 Access UI at: http://$PUBLIC_IP:5000"

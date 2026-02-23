import subprocess
import time
import sys
import os
import requests

def run_system():
    # Paths
    base_dir = os.path.dirname(os.path.abspath(__file__))
    master_script = os.path.join(base_dir, 'master_node', 'app.py')
    storage_script = os.path.join(base_dir, 'storage_node', 'server.py')
    python_exe = sys.executable 

    print(f"Using Python: {python_exe}")
    
    processes = []

    try:
        # Start Master Node
        print("Starting Master Node on port 5000...")
        p_master = subprocess.Popen([python_exe, master_script], cwd=os.path.join(base_dir, 'master_node'))
        processes.append(p_master)
        
        # Start Storage Node 1
        print("Starting Storage Node 1 on port 5001...")
        p_storage1 = subprocess.Popen([python_exe, storage_script, '5001'], cwd=os.path.join(base_dir, 'storage_node'))
        processes.append(p_storage1)
        
        # Start Storage Node 2
        print("Starting Storage Node 2 on port 5002...")
        p_storage2 = subprocess.Popen([python_exe, storage_script, '5002'], cwd=os.path.join(base_dir, 'storage_node'))
        processes.append(p_storage2)

        # Wait for them to spin up
        time.sleep(3)

        # Register Storage Nodes with Master
        try:
            key = os.environ.get('NODE_REGISTRATION_KEY', 'default_cluster_secret')
            requests.post('http://localhost:5000/api/register_node', json={'name': 'Node 1', 'address': 'http://localhost:5001', 'node_key': key})
            print("Registered Node 1")
            requests.post('http://localhost:5000/api/register_node', json={'name': 'Node 2', 'address': 'http://localhost:5002', 'node_key': key})
            print("Registered Node 2")
        except Exception as e:
            print(f"Failed to register nodes: {e}")

        print("\nSystem is running!")
        print("Master Node: http://localhost:5000")
        print("Storage Node 1: http://localhost:5001")
        print("Storage Node 2: http://localhost:5002")
        print("Press Ctrl+C to stop.")
        
        # Keep alive
        p_master.wait()

    except KeyboardInterrupt:
        print("\nStopping system...")
    finally:
        for p in processes:
            p.terminate()

if __name__ == '__main__':
    run_system()

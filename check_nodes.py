import requests
import sys

def check_nodes(master_ip):
    url = f"http://{master_ip}:5000/api/nodes"
    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        data = response.json()
        
        nodes = data.get('nodes', [])
        
        print("\n" + "="*50)
        print(f"Connected Storage Nodes (Total: {len(nodes)})")
        print("="*50)
        
        if not nodes:
            print("No nodes are currently registered.")
        else:
            for n in nodes:
                print(f"Name   : {n['name']}")
                print(f"Address: {n['address']}")
                print(f"Status : {n['status']}")
                print(f"Last Ping: {n['last_heartbeat']}")
                print("-" * 30)
                
    except requests.exceptions.ConnectionError:
        print(f"Error: Could not connect to Master Node at {master_ip}:5000")
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python check_nodes.py <MASTER_IP>")
        print("Example: python check_nodes.py 127.0.0.1")
        sys.exit(1)
        
    master_ip = sys.argv[1]
    check_nodes(master_ip)

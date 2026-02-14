import sqlite3
import os

DB_PATH = 'metadata.db'

def get_db_connection():
    conn = sqlite3.connect(DB_PATH, timeout=10) # Increase timeout
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA journal_mode=WAL;') # Enable WAL mode for concurrency
    return conn

def init_db():
    # Remove old DB if exists because schema is changing
    if os.path.exists(DB_PATH):
        try:
            os.remove(DB_PATH)
            print("Old database removed.")
        except:
            pass

    conn = get_db_connection()
    with conn:
        conn.executescript('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                is_admin BOOLEAN DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS storage_nodes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                address TEXT UNIQUE NOT NULL,
                status TEXT DEFAULT 'active',
                last_heartbeat TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT NOT NULL,
                user_id INTEGER NOT NULL,
                size INTEGER NOT NULL,
                uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id)
            );

            CREATE TABLE IF NOT EXISTS chunks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_id INTEGER NOT NULL,
                sequence INTEGER NOT NULL,
                storage_node_id INTEGER NOT NULL,
                chunk_id TEXT NOT NULL,
                FOREIGN KEY (file_id) REFERENCES files (id),
                FOREIGN KEY (storage_node_id) REFERENCES storage_nodes (id)
            );
        ''')
    conn.close()
    print("Database (re)initialized with Chunking schema.")

if __name__ == '__main__':
    init_db()

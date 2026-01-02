import sqlite3
import os

# 1. Dynamically determine the project root directory
# This script is in: backend/utils/db_init.py
# __file__ is the full path to this script.
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 2. Define absolute paths to your resources
DB_PATH = os.path.join(BASE_DIR, 'database', 'rupx.db')
SCHEMA_PATH = os.path.join(BASE_DIR, 'database', 'schema.sql')

def get_db():
    """Get database connection with an absolute path"""
    # Ensure the directory for the DB exists
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initialize database using the absolute schema path"""
    if not os.path.exists(SCHEMA_PATH):
        print(f"❌ Error: Schema file not found at {SCHEMA_PATH}")
        return

    try:
        conn = get_db()
        cursor = conn.cursor()
        
        with open(SCHEMA_PATH, 'r') as f:
            schema = f.read()
            cursor.executescript(schema)
        
        conn.commit()
        conn.close()
        print(f"✅ Database initialized successfully at: {DB_PATH}")
    except Exception as e:
        print(f"❌ Failed to initialize database: {e}")

if __name__ == '__main__':
    init_db()
import sqlite3
import os

# Get the project root directory (where backend/ folder is)
# This script is in: backend/utils/db_init.py
# Go up 2 levels to reach project root
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Use 'storage' directory instead of 'database'
DB_PATH = os.path.join(BASE_DIR, 'storage', 'rupx.db')
SCHEMA_PATH = os.path.join(BASE_DIR, 'database', 'schema.sql')

def get_db():
    """Get database connection with absolute path to storage/rupx.db"""
    # Ensure the storage directory exists
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initialize database using schema.sql"""
    if not os.path.exists(SCHEMA_PATH):
        print(f"❌ Error: Schema file not found at {SCHEMA_PATH}")
        print(f"   Looking for: {SCHEMA_PATH}")
        return

    try:
        conn = get_db()
        cursor = conn.cursor()
        
        print(f"📂 Using database at: {DB_PATH}")
        print(f"📄 Reading schema from: {SCHEMA_PATH}")
        
        with open(SCHEMA_PATH, 'r', encoding='utf-8') as f:
            schema = f.read()
            cursor.executescript(schema)
        
        conn.commit()
        conn.close()
        print(f"✅ Database initialized successfully!")
        print(f"   Location: {DB_PATH}")
    except Exception as e:
        print(f"❌ Failed to initialize database: {e}")
        import traceback
        traceback.print_exc()

def verify_schema():
    """Verify that all tables and columns exist"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        print("\n🔍 Verifying database schema...")
        
        # Check users table
        cursor.execute("PRAGMA table_info(users)")
        users_cols = [col[1] for col in cursor.fetchall()]
        print(f"   Users table columns: {', '.join(users_cols)}")
        
        # Verify 'verified' column exists
        if 'verified' in users_cols:
            print("   ✅ 'verified' column exists")
        else:
            print("   ❌ 'verified' column missing!")
        
        # Check projects table
        cursor.execute("PRAGMA table_info(projects)")
        projects_cols = [col[1] for col in cursor.fetchall()]
        print(f"   Projects table columns: {', '.join(projects_cols)}")
        
        # Check all tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        print(f"   Tables in database: {', '.join(tables)}")
        
        conn.close()
        print("✅ Schema verification complete!\n")
        
    except Exception as e:
        print(f"❌ Error verifying schema: {e}")

if __name__ == '__main__':
    print("="*60)
    print("RupX Database Initialization")
    print("="*60)
    init_db()
    verify_schema()
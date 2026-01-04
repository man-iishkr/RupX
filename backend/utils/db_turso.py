"""
Turso (Cloud SQLite) Database Connection
Uses libsql (not libsql-experimental) for compatibility
"""
import libsql
import os
from dotenv import load_dotenv

load_dotenv()

TURSO_DATABASE_URL = os.getenv('TURSO_DATABASE_URL')
TURSO_AUTH_TOKEN = os.getenv('TURSO_AUTH_TOKEN')

# Validate credentials
if not TURSO_DATABASE_URL or not TURSO_AUTH_TOKEN:
    print("⚠️  Warning: TURSO_DATABASE_URL or TURSO_AUTH_TOKEN not set")
    print("   Falling back to local SQLite")

def get_db():
    """Get Turso database connection"""
    if not TURSO_DATABASE_URL or not TURSO_AUTH_TOKEN:
        raise ValueError("Turso credentials not configured")
    
    try:
        # Connect to Turso
        conn = libsql.connect(
            database=TURSO_DATABASE_URL,
            auth_token=TURSO_AUTH_TOKEN
        )
        
        # Enable dict-like row access
        conn.row_factory = libsql.Row
        
        return conn
    except Exception as e:
        print(f"❌ Error connecting to Turso: {e}")
        raise

def init_db():
    """Initialize Turso database with schema"""
    print("🔧 Initializing Turso database...")
    
    # Get schema path
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    schema_path = os.path.join(base_dir, 'database', 'schema.sql')
    
    if not os.path.exists(schema_path):
        print(f"❌ Schema file not found at: {schema_path}")
        raise FileNotFoundError(f"Schema file not found: {schema_path}")
    
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Read and execute schema
        with open(schema_path, 'r', encoding='utf-8') as f:
            schema = f.read()
            
            # Split schema into individual statements
            statements = [s.strip() for s in schema.split(';') if s.strip()]
            
            for statement in statements:
                if statement:
                    try:
                        cursor.execute(statement)
                    except Exception as stmt_error:
                        # Some statements might fail if tables already exist
                        if 'already exists' not in str(stmt_error).lower():
                            print(f"⚠️  Warning executing statement: {stmt_error}")
        
        conn.commit()
        print("✅ Turso database initialized successfully")
        
        # Verify tables were created
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        print(f"📋 Created tables: {', '.join([t[0] for t in tables])}")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ Error initializing Turso database: {e}")
        import traceback
        traceback.print_exc()
        raise

def verify_connection():
    """Verify Turso connection is working"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        return result[0] == 1
    except Exception as e:
        print(f"❌ Turso connection verification failed: {e}")
        return False

if __name__ == '__main__':
    print("=" * 60)
    print("Turso Database Initialization")
    print("=" * 60)
    
    # Check credentials
    if not TURSO_DATABASE_URL or not TURSO_AUTH_TOKEN:
        print("❌ Turso credentials not found in environment variables")
        print("   Please set TURSO_DATABASE_URL and TURSO_AUTH_TOKEN")
        exit(1)
    
    print(f"Database URL: {TURSO_DATABASE_URL[:30]}...")
    print(f"Auth Token: {TURSO_AUTH_TOKEN[:20]}...")
    
    # Verify connection
    print("\n🔍 Verifying connection...")
    if verify_connection():
        print("✅ Connection successful")
    else:
        print("❌ Connection failed")
        exit(1)
    
    # Initialize database
    print("\n📝 Initializing database schema...")
    init_db()
    
    print("\n" + "=" * 60)
    print("✅ Turso database setup complete!")
    print("=" * 60)
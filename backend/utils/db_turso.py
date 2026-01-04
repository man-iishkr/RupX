"""
Turso (Cloud SQLite) Database Connection
Uses libsql for compatibility with Render deployment
Properly handles both tuple and dict returns
"""
import libsql
import os
from dotenv import load_dotenv

load_dotenv()

TURSO_DATABASE_URL = os.getenv('TURSO_DATABASE_URL')
TURSO_AUTH_TOKEN = os.getenv('TURSO_AUTH_TOKEN')

if not TURSO_DATABASE_URL or not TURSO_AUTH_TOKEN:
    print("⚠️  Warning: TURSO_DATABASE_URL or TURSO_AUTH_TOKEN not set")

class TursoConnection:
    """Wrapper for libsql connection that provides dict-like row access"""
    
    def __init__(self, conn):
        self._conn = conn
    
    def cursor(self):
        return TursoCursor(self._conn.cursor())
    
    def commit(self):
        return self._conn.commit()
    
    def rollback(self):
        return self._conn.rollback()
    
    def close(self):
        return self._conn.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


class TursoCursor:
    """Cursor wrapper that returns rows as dicts"""
    
    def __init__(self, cursor):
        self._cursor = cursor
    
    @property
    def description(self):
        return self._cursor.description
    
    @property
    def rowcount(self):
        return self._cursor.rowcount
    
    def _to_dict(self, row):
        """Convert tuple row to dict using column names"""
        if row is None:
            return None
        if not self.description:
            return row
        return {col[0]: row[i] for i, col in enumerate(self.description)}
    
    def execute(self, query, params=None):
        try:
            if params:
                return self._cursor.execute(query, params)
            return self._cursor.execute(query)
        except Exception as e:
            print(f"❌ Execute error: {e}")
            print(f"   Query: {query[:100]}")
            raise
    
    def executescript(self, script):
        return self._cursor.executescript(script)
    
    def fetchone(self):
        row = self._cursor.fetchone()
        return self._to_dict(row)
    
    def fetchall(self):
        rows = self._cursor.fetchall()
        if not rows:
            return []
        return [self._to_dict(row) for row in rows]
    
    def fetchmany(self, size=None):
        rows = self._cursor.fetchmany(size) if size else self._cursor.fetchmany()
        if not rows:
            return []
        return [self._to_dict(row) for row in rows]
    
    def close(self):
        return self._cursor.close()


def get_db():
    """Get Turso database connection"""
    if not TURSO_DATABASE_URL or not TURSO_AUTH_TOKEN:
        raise ValueError("Turso credentials not configured. Set TURSO_DATABASE_URL and TURSO_AUTH_TOKEN")
    
    try:
        conn = libsql.connect(
            database=TURSO_DATABASE_URL,
            auth_token=TURSO_AUTH_TOKEN
        )
        return TursoConnection(conn)
    except Exception as e:
        print(f"❌ Error connecting to Turso: {e}")
        raise


def init_db():
    """Initialize Turso database with schema"""
    print("🔧 Initializing Turso database...")
    
    # Find schema file
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    schema_path = os.path.join(base_dir, 'database', 'schema.sql')
    
    if not os.path.exists(schema_path):
        raise FileNotFoundError(f"Schema file not found: {schema_path}")
    
    conn = None
    cursor = None
    
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Read schema
        with open(schema_path, 'r', encoding='utf-8') as f:
            schema = f.read()
        
        # Execute schema statements one by one
        statements = [s.strip() for s in schema.split(';') if s.strip()]
        
        for i, statement in enumerate(statements):
            if not statement:
                continue
            
            try:
                cursor.execute(statement)
                conn.commit()
            except Exception as stmt_error:
                error_msg = str(stmt_error).lower()
                # Ignore "already exists" errors
                if 'already exists' in error_msg or 'duplicate' in error_msg:
                    continue
                else:
                    print(f"⚠️  Warning on statement {i+1}: {stmt_error}")
        
        print("✅ Schema executed successfully")
        
        # Verify tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        tables = cursor.fetchall()
        
        if tables:
            # Handle both dict and tuple responses
            if isinstance(tables[0], dict):
                table_names = [t['name'] for t in tables]
            else:
                table_names = [t[0] for t in tables]
            
            print(f"📋 Tables: {', '.join(table_names)}")
        else:
            print("⚠️  No tables found after initialization")
        
    except Exception as e:
        print(f"❌ Error initializing database: {e}")
        import traceback
        traceback.print_exc()
        raise
    
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


def verify_connection():
    """Test database connection"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT 1 as test")
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        
        # Handle both dict and tuple
        if isinstance(result, dict):
            return result.get('test') == 1
        else:
            return result[0] == 1
    except Exception as e:
        print(f"❌ Connection test failed: {e}")
        return False


if __name__ == '__main__':
    print("=" * 60)
    print("Turso Database Setup")
    print("=" * 60)
    
    if not TURSO_DATABASE_URL or not TURSO_AUTH_TOKEN:
        print("❌ Missing credentials")
        print("   Set TURSO_DATABASE_URL and TURSO_AUTH_TOKEN")
        exit(1)
    
    print(f"URL: {TURSO_DATABASE_URL[:50]}...")
    print(f"Token: {TURSO_AUTH_TOKEN[:20]}...")
    
    print("\n🔍 Testing connection...")
    if not verify_connection():
        print("❌ Connection failed")
        exit(1)
    
    print("✅ Connection OK")
    
    print("\n📝 Initializing schema...")
    init_db()
    
    print("\n" + "=" * 60)
    print("✅ Setup complete")
    print("=" * 60)
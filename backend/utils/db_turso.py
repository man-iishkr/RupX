"""
Turso (Cloud SQLite) Database Connection
Fixed: Maps libsql_client sync methods to standard cursor-like behavior
"""
import libsql_client 
import os
from dotenv import load_dotenv

load_dotenv()

TURSO_DATABASE_URL = os.getenv('TURSO_DATABASE_URL')
TURSO_AUTH_TOKEN = os.getenv('TURSO_AUTH_TOKEN')

if not TURSO_DATABASE_URL or not TURSO_AUTH_TOKEN:
    print("⚠️  Warning: TURSO_DATABASE_URL or TURSO_AUTH_TOKEN not set")

class TursoConnection:
    """Wrapper for libsql_client to simulate a standard DB-API connection"""
    
    def __init__(self, client):
        self._client = client
    
    def cursor(self):
        # We pass the client to the cursor since the client is what executes queries
        return TursoCursor(self._client)
    
    def commit(self):
        # Turso/libsql_client handles commits automatically for standard executes
        pass
    
    def rollback(self):
        pass
    
    def close(self):
        return self._client.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


class TursoCursor:
    """Cursor wrapper that translates client results into dicts and supports iteration"""
    
    def __init__(self, client):
        self._client = client
        self.description = None
        self.rowcount = -1
        self._results = []
    
    def _to_dict(self, row, columns):
        """Helper to convert a single row into a dictionary"""
        if row is None:
            return None
        return {col: row[i] for i, col in enumerate(columns)}
    
    def execute(self, query, params=None):
        try:
            # libsql_client uses .execute(query, positional_params)
            res = self._client.execute(query, params or [])
            
            # Update cursor metadata
            self.description = [[col] for col in res.columns]
            self.rowcount = len(res.rows)
            
            # Convert all rows to dicts immediately for fetchone/fetchall
            self._results = [self._to_dict(row, res.columns) for row in res.rows]
            return res
        except Exception as e:
            print(f"❌ Execute error: {e}")
            print(f"   Query: {query[:100]}")
            raise
    
    def executescript(self, script):
        """Batch execution for schema files"""
        try:
            statements = [s.strip() for s in script.split(';') if s.strip()]
            for stmt in statements:
                self._client.execute(stmt)
        except Exception as e:
            print(f"❌ Script error: {e}")
            raise
    
    def fetchone(self):
        if not self._results:
            return None
        return self._results.pop(0)
    
    def fetchall(self):
        rows = list(self._results)
        self._results = []
        return rows
    
    def fetchmany(self, size=1):
        rows = self._results[:size]
        self._results = self._results[size:]
        return rows
    
    def close(self):
        pass


def get_db():
    if not TURSO_DATABASE_URL or not TURSO_AUTH_TOKEN:
        raise ValueError("Turso credentials not configured. Set TURSO_DATABASE_URL and TURSO_AUTH_TOKEN")
    
    try:
        # Use create_client_sync to avoid the tokio-runtime panic
        client = libsql_client.create_client_sync(
            url=TURSO_DATABASE_URL,
            auth_token=TURSO_AUTH_TOKEN
        )
        return TursoConnection(client)
    except Exception as e:
        print(f"❌ Error connecting to Turso: {e}")
        raise

# Keep all your existing init_db, verify_connection, and __main__ logic below...
# They will now work because conn.cursor() is no longer an AttributeError.

def init_db():
    """Initialize Turso database with schema"""
    print("🔧 Initializing Turso database...")
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    schema_path = os.path.join(base_dir, 'database', 'schema.sql')
    
    if not os.path.exists(schema_path):
        raise FileNotFoundError(f"Schema file not found: {schema_path}")
    
    conn = None
    cursor = None
    try:
        conn = get_db()
        cursor = conn.cursor()
        with open(schema_path, 'r', encoding='utf-8') as f:
            schema = f.read()
        
        statements = [s.strip() for s in schema.split(';') if s.strip()]
        for i, statement in enumerate(statements):
            if not statement: continue
            try:
                cursor.execute(statement)
            except Exception as stmt_error:
                if 'already exists' in str(stmt_error).lower(): continue
                print(f"⚠️  Warning on statement {i+1}: {stmt_error}")
        
        print("✅ Schema executed successfully")
    except Exception as e:
        print(f"❌ Error initializing database: {e}")
        raise
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

def verify_connection():
    """Test database connection"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT 1 as test")
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        return result.get('test') == 1 if isinstance(result, dict) else result[0] == 1
    except Exception as e:
        print(f"❌ Connection test failed: {e}")
        return False

if __name__ == '__main__':
    # ... rest of your testing code remains the same ...
    print("\n🔍 Testing connection...")
    if verify_connection():
        print("✅ Connection OK")
        init_db()
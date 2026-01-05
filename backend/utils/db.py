"""
Unified Database Adapter
Automatically uses Turso (production) or SQLite (development)
"""
import os

if os.getenv('TURSO_DATABASE_URL') and os.getenv('TURSO_AUTH_TOKEN'):
    from utils.db_turso import get_db, init_db
    DB_TYPE = 'turso'
    print("📊 Using Turso (Cloud SQLite)")
else:
    from utils.db_init import get_db, init_db
    DB_TYPE = 'sqlite'
    print("📊 Using Local SQLite")

__all__ = ['get_db', 'init_db', 'DB_TYPE']
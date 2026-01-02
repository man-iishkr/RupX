-- RupX Database Schema

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    created_at TEXT NOT NULL,
    last_login TEXT
);

CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    created_at TEXT NOT NULL,
    is_active INTEGER DEFAULT 0,
    dataset_uploaded INTEGER DEFAULT 0,
    model_trained INTEGER DEFAULT 0,
    attendance_mode TEXT DEFAULT 'daily',
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE(user_id, name)
);

CREATE TABLE IF NOT EXISTS training_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    status TEXT NOT NULL,
    num_identities INTEGER DEFAULT 0,
    images_processed INTEGER DEFAULT 0,
    images_skipped INTEGER DEFAULT 0,
    duration_seconds REAL,
    accuracy REAL,
    precision REAL,
    error_message TEXT,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS attendance_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    marked_at TEXT NOT NULL,
    session_id TEXT,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_projects_user ON projects(user_id);
CREATE INDEX IF NOT EXISTS idx_projects_active ON projects(user_id, is_active);
CREATE INDEX IF NOT EXISTS idx_attendance_project ON attendance_records(project_id);
CREATE INDEX IF NOT EXISTS idx_attendance_date ON attendance_records(marked_at);
CREATE TABLE branches(id TEXT PRIMARY KEY,name TEXT NOT NULL,token_hash TEXT UNIQUE NOT NULL,active INTEGER NOT NULL DEFAULT 1,revision INTEGER NOT NULL DEFAULT 0,received_at TEXT,payload TEXT,device_id TEXT);
CREATE TABLE sessions(token_hash TEXT PRIMARY KEY,expires INTEGER NOT NULL);
CREATE INDEX session_expiry ON sessions(expires);
CREATE TABLE attempts(key TEXT PRIMARY KEY,failures INTEGER NOT NULL,until_at INTEGER NOT NULL);

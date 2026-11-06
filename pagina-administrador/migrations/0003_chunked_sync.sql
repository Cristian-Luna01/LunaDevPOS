CREATE TABLE IF NOT EXISTS sync_parts(
 branch_id TEXT NOT NULL,upload_id TEXT NOT NULL,part INTEGER NOT NULL,data TEXT NOT NULL,
 created_at INTEGER NOT NULL,PRIMARY KEY(branch_id,upload_id,part));
CREATE INDEX IF NOT EXISTS sync_parts_age ON sync_parts(created_at);
CREATE TABLE IF NOT EXISTS sync_uploads(
 branch_id TEXT NOT NULL,upload_id TEXT NOT NULL,kind TEXT NOT NULL,revision INTEGER NOT NULL,
 device_id TEXT NOT NULL,parts INTEGER NOT NULL,sha256 TEXT NOT NULL,created_at INTEGER NOT NULL,
 PRIMARY KEY(branch_id,upload_id));

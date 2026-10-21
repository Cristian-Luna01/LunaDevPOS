CREATE TABLE IF NOT EXISTS upload_parts(branch_id TEXT NOT NULL,upload_id TEXT NOT NULL,part INTEGER NOT NULL,total INTEGER NOT NULL,kind TEXT NOT NULL,digest TEXT NOT NULL,data TEXT NOT NULL,created_at INTEGER NOT NULL,PRIMARY KEY(branch_id,upload_id,part));
CREATE INDEX IF NOT EXISTS uploads_created ON upload_parts(created_at);
CREATE TABLE IF NOT EXISTS document_chunks(branch_id TEXT NOT NULL,blob_id TEXT NOT NULL,part INTEGER NOT NULL,data TEXT NOT NULL,created_at INTEGER NOT NULL,PRIMARY KEY(branch_id,blob_id,part));
CREATE INDEX IF NOT EXISTS chunks_created ON document_chunks(created_at);

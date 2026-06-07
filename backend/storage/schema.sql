-- Videos table
-- Stores metadata for processed videos
CREATE TABLE IF NOT EXISTS videos (
    id TEXT PRIMARY KEY,              -- BV number or aweme_id
    platform TEXT NOT NULL,           -- 'bilibili' or 'douyin'
    title TEXT NOT NULL,
    author TEXT,
    duration INTEGER,                 -- Duration in seconds
    url TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',  -- pending/processing/completed/failed
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    processed_at TIMESTAMP
);

-- Documents table
-- Stores markdown documents generated from videos
CREATE TABLE IF NOT EXISTS documents (
    id TEXT PRIMARY KEY,
    video_id TEXT NOT NULL,
    file_path TEXT NOT NULL,         -- Path to markdown file
    chunk_count INTEGER DEFAULT 0,   -- Number of chunks created
    is_indexed BOOLEAN DEFAULT 0,    -- Whether indexed in Qdrant
    indexed_at TIMESTAMP,
    FOREIGN KEY (video_id) REFERENCES videos(id) ON DELETE CASCADE
);

-- Configuration table
-- Stores app configuration key-value pairs
CREATE TABLE IF NOT EXISTS config (
    key TEXT PRIMARY KEY,
    value TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for common queries
CREATE INDEX IF NOT EXISTS idx_videos_status ON videos(status);
CREATE INDEX IF NOT EXISTS idx_videos_platform ON videos(platform);
CREATE INDEX IF NOT EXISTS idx_documents_video_id ON documents(video_id);

-- Videos table
-- Stores metadata for processed videos
CREATE TABLE IF NOT EXISTS videos (
    id TEXT PRIMARY KEY,              -- BV number or aweme_id
    platform TEXT NOT NULL,           -- 'bilibili' or 'douyin'
    title TEXT NOT NULL,
    author TEXT,
    author_id TEXT,
    duration INTEGER,                 -- Duration in seconds
    url TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',  -- pending/processing/completed/failed
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    processed_at TIMESTAMP
);

-- Documents table
-- Stores markdown documents generated from videos
CREATE TABLE IF NOT EXISTS documents (
    id TEXT PRIMARY KEY,
    video_id TEXT,                       -- nullable: documents can stand alone
    file_path TEXT NOT NULL,         -- Path to markdown file
    chunk_count INTEGER DEFAULT 0,   -- Number of chunks created
    status TEXT DEFAULT 'raw',        -- Processing status: raw/indexed
    indexed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (video_id) REFERENCES videos(id) ON DELETE SET NULL
);

-- Configuration table
-- Stores app configuration key-value pairs
CREATE TABLE IF NOT EXISTS config (
    key TEXT PRIMARY KEY,
    value TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Model presets table
-- Stores transcription model configurations grouped by model_name
CREATE TABLE IF NOT EXISTS model_presets (
    id TEXT PRIMARY KEY,
    model_name TEXT NOT NULL,
    name TEXT NOT NULL,
    config TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(model_name, name)
);

-- Active preset table
-- Tracks the currently active preset for each model
CREATE TABLE IF NOT EXISTS active_preset (
    model_name TEXT PRIMARY KEY,
    preset_id TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (preset_id) REFERENCES model_presets(id) ON DELETE SET NULL
);

-- App config table
-- General key-value configuration storage
CREATE TABLE IF NOT EXISTS app_config (
    key TEXT PRIMARY KEY,
    value TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for common queries
CREATE INDEX IF NOT EXISTS idx_videos_status ON videos(status);
CREATE INDEX IF NOT EXISTS idx_videos_platform ON videos(platform);
CREATE INDEX IF NOT EXISTS idx_documents_video_id ON documents(video_id);

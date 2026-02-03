-- Bomagi Interior Inspiration Database Schema

CREATE TABLE IF NOT EXISTS images (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    -- Source info
    source TEXT NOT NULL,  -- 'civitai', 'lexica', 'midjourney', 'finn', 'pinterest'
    source_id TEXT,        -- Original ID from source
    source_url TEXT,       -- Original page URL

    -- Image data
    image_url TEXT NOT NULL,
    local_path TEXT,       -- Local file path after download
    thumbnail_url TEXT,

    -- Metadata
    title TEXT,
    description TEXT,
    prompt TEXT,           -- AI generation prompt (if available)

    -- Classification
    room_type TEXT,        -- 'living_room', 'kitchen', 'bedroom', 'bathroom', 'hallway', 'dining', 'office', 'outdoor', 'other'
    style_tags TEXT,       -- JSON array of style tags

    -- Quality metrics
    width INTEGER,
    height INTEGER,
    quality_score REAL,    -- 0-1 computed score
    engagement INTEGER,    -- Likes/views from source

    -- Curation
    status TEXT DEFAULT 'pending',  -- 'pending', 'approved', 'rejected'
    curated_at DATETIME,
    notes TEXT,

    -- Timestamps
    scraped_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(source, source_id)
);

CREATE TABLE IF NOT EXISTS scrape_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    query TEXT,
    room_type TEXT,
    images_found INTEGER DEFAULT 0,
    images_new INTEGER DEFAULT 0,
    started_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    completed_at DATETIME,
    status TEXT DEFAULT 'running',  -- 'running', 'completed', 'failed'
    error TEXT
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_images_source ON images(source);
CREATE INDEX IF NOT EXISTS idx_images_room_type ON images(room_type);
CREATE INDEX IF NOT EXISTS idx_images_status ON images(status);
CREATE INDEX IF NOT EXISTS idx_images_quality ON images(quality_score DESC);
CREATE INDEX IF NOT EXISTS idx_images_engagement ON images(engagement DESC);

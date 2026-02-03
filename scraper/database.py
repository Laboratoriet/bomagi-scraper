"""Database interface for Bomagi scraper."""
import sqlite3
import json
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any
from contextlib import contextmanager

DB_PATH = Path(__file__).parent.parent / "db" / "bomagi.db"
SCHEMA_PATH = Path(__file__).parent.parent / "db" / "schema.sql"


def init_db():
    """Initialize database with schema."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with get_connection() as conn:
        with open(SCHEMA_PATH) as f:
            conn.executescript(f.read())


@contextmanager
def get_connection():
    """Context manager for database connections."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def image_exists(source: str, source_id: str) -> bool:
    """Check if image already exists in database."""
    with get_connection() as conn:
        result = conn.execute(
            "SELECT 1 FROM images WHERE source = ? AND source_id = ?",
            (source, source_id)
        ).fetchone()
        return result is not None


def insert_image(data: Dict[str, Any]) -> int:
    """Insert new image record. Returns row ID."""
    with get_connection() as conn:
        # Convert style_tags list to JSON if present
        if 'style_tags' in data and isinstance(data['style_tags'], list):
            data['style_tags'] = json.dumps(data['style_tags'])

        columns = ', '.join(data.keys())
        placeholders = ', '.join(['?' for _ in data])
        values = list(data.values())

        cursor = conn.execute(
            f"INSERT OR IGNORE INTO images ({columns}) VALUES ({placeholders})",
            values
        )
        return cursor.lastrowid


def update_image(image_id: int, data: Dict[str, Any]):
    """Update image record."""
    with get_connection() as conn:
        if 'style_tags' in data and isinstance(data['style_tags'], list):
            data['style_tags'] = json.dumps(data['style_tags'])

        set_clause = ', '.join([f"{k} = ?" for k in data.keys()])
        values = list(data.values()) + [image_id]

        conn.execute(
            f"UPDATE images SET {set_clause} WHERE id = ?",
            values
        )


def get_images(
    source: Optional[str] = None,
    room_type: Optional[str] = None,
    status: Optional[str] = None,
    min_quality: Optional[float] = None,
    limit: int = 100,
    offset: int = 0,
    order_by: str = "scraped_at DESC"
) -> List[Dict]:
    """Get images with optional filters."""
    with get_connection() as conn:
        conditions = []
        params = []

        if source:
            conditions.append("source = ?")
            params.append(source)
        if room_type:
            conditions.append("room_type = ?")
            params.append(room_type)
        if status:
            conditions.append("status = ?")
            params.append(status)
        if min_quality is not None:
            conditions.append("quality_score >= ?")
            params.append(min_quality)

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        query = f"""
            SELECT * FROM images
            {where_clause}
            ORDER BY {order_by}
            LIMIT ? OFFSET ?
        """
        params.extend([limit, offset])

        rows = conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]


def get_stats() -> Dict[str, Any]:
    """Get database statistics."""
    with get_connection() as conn:
        total = conn.execute("SELECT COUNT(*) FROM images").fetchone()[0]
        by_source = dict(conn.execute(
            "SELECT source, COUNT(*) FROM images GROUP BY source"
        ).fetchall())
        by_room = dict(conn.execute(
            "SELECT room_type, COUNT(*) FROM images WHERE room_type IS NOT NULL GROUP BY room_type"
        ).fetchall())
        by_status = dict(conn.execute(
            "SELECT status, COUNT(*) FROM images GROUP BY status"
        ).fetchall())

        return {
            "total": total,
            "by_source": by_source,
            "by_room_type": by_room,
            "by_status": by_status
        }


def start_scrape_run(source: str, query: str = None, room_type: str = None) -> int:
    """Start a new scrape run. Returns run ID."""
    with get_connection() as conn:
        cursor = conn.execute(
            "INSERT INTO scrape_runs (source, query, room_type) VALUES (?, ?, ?)",
            (source, query, room_type)
        )
        return cursor.lastrowid


def complete_scrape_run(run_id: int, images_found: int, images_new: int, error: str = None):
    """Mark scrape run as completed."""
    with get_connection() as conn:
        status = "failed" if error else "completed"
        conn.execute(
            """UPDATE scrape_runs
               SET completed_at = ?, images_found = ?, images_new = ?, status = ?, error = ?
               WHERE id = ?""",
            (datetime.now(), images_found, images_new, status, error, run_id)
        )


def get_image_by_id(image_id: int) -> Optional[Dict]:
    """Get a single image by ID."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM images WHERE id = ?",
            (image_id,)
        ).fetchone()
        return dict(row) if row else None


def get_images_for_download(
    status: str = 'approved',
    room_type: str = None,
    source: str = None,
    only_missing: bool = True
) -> List[Dict]:
    """
    Get images that need to be downloaded.

    Args:
        status: Filter by status
        room_type: Filter by room type
        source: Filter by source
        only_missing: Only return images without local_path

    Returns:
        List of image records
    """
    with get_connection() as conn:
        conditions = []
        params = []

        if status:
            conditions.append("status = ?")
            params.append(status)
        if room_type:
            conditions.append("room_type = ?")
            params.append(room_type)
        if source:
            conditions.append("source = ?")
            params.append(source)
        if only_missing:
            conditions.append("(local_path IS NULL OR local_path = '')")

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        rows = conn.execute(f"""
            SELECT * FROM images
            {where_clause}
            ORDER BY quality_score DESC
        """, params).fetchall()

        return [dict(row) for row in rows]


def bulk_update_status(image_ids: List[int], status: str, notes: str = None):
    """Update status for multiple images at once."""
    with get_connection() as conn:
        for image_id in image_ids:
            if notes:
                conn.execute(
                    "UPDATE images SET status = ?, notes = ?, curated_at = ? WHERE id = ?",
                    (status, notes, datetime.now(), image_id)
                )
            else:
                conn.execute(
                    "UPDATE images SET status = ?, curated_at = ? WHERE id = ?",
                    (status, datetime.now(), image_id)
                )


def get_download_stats() -> Dict[str, int]:
    """Get statistics about downloaded vs pending images."""
    with get_connection() as conn:
        total = conn.execute("SELECT COUNT(*) FROM images").fetchone()[0]
        downloaded = conn.execute(
            "SELECT COUNT(*) FROM images WHERE local_path IS NOT NULL AND local_path != ''"
        ).fetchone()[0]
        approved = conn.execute(
            "SELECT COUNT(*) FROM images WHERE status = 'approved'"
        ).fetchone()[0]
        approved_downloaded = conn.execute(
            "SELECT COUNT(*) FROM images WHERE status = 'approved' AND local_path IS NOT NULL"
        ).fetchone()[0]

        return {
            "total": total,
            "downloaded": downloaded,
            "pending_download": total - downloaded,
            "approved": approved,
            "approved_downloaded": approved_downloaded,
            "approved_pending": approved - approved_downloaded,
        }

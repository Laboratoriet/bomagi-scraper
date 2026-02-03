"""
Perceptual hash-based image deduplication.

Uses multiple hashing algorithms to detect near-duplicate images:
- pHash (perceptual hash) - best for finding similar images
- dHash (difference hash) - fast and good for exact/near-exact duplicates
- aHash (average hash) - simplest, catches obvious duplicates

Images are considered duplicates if their hash distance is below a threshold.
"""

import os
from typing import Optional, List, Dict, Tuple, Set
from pathlib import Path
from collections import defaultdict

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

try:
    import imagehash
    HAS_IMAGEHASH = True
except ImportError:
    HAS_IMAGEHASH = False

try:
    import requests
    from io import BytesIO
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False


# Hash size (bits = size^2, so 16 gives 256-bit hash)
HASH_SIZE = 16

# Distance thresholds for considering images as duplicates
# Lower = stricter matching
THRESHOLDS = {
    'exact': 0,        # Identical images
    'near_exact': 3,   # Virtually identical (resize, minor compression)
    'similar': 8,      # Very similar (crops, slight edits)
    'loose': 12,       # Loosely similar (may have false positives)
}

DEFAULT_THRESHOLD = THRESHOLDS['similar']


def compute_phash(image_source, hash_size: int = HASH_SIZE) -> Optional[str]:
    """
    Compute perceptual hash for an image.

    Args:
        image_source: Path, URL, or PIL Image
        hash_size: Size of hash (larger = more precise but slower)

    Returns:
        Hex string of the hash, or None on error
    """
    if not HAS_PIL or not HAS_IMAGEHASH:
        raise ImportError("PIL and imagehash required. Run: pip install Pillow imagehash")

    try:
        image = _load_image(image_source)
        phash = imagehash.phash(image, hash_size=hash_size)
        return str(phash)
    except Exception as e:
        print(f"Hash error for {image_source}: {e}")
        return None


def compute_dhash(image_source, hash_size: int = HASH_SIZE) -> Optional[str]:
    """Compute difference hash for an image."""
    if not HAS_PIL or not HAS_IMAGEHASH:
        raise ImportError("PIL and imagehash required")

    try:
        image = _load_image(image_source)
        dhash = imagehash.dhash(image, hash_size=hash_size)
        return str(dhash)
    except Exception:
        return None


def compute_ahash(image_source, hash_size: int = HASH_SIZE) -> Optional[str]:
    """Compute average hash for an image."""
    if not HAS_PIL or not HAS_IMAGEHASH:
        raise ImportError("PIL and imagehash required")

    try:
        image = _load_image(image_source)
        ahash = imagehash.average_hash(image, hash_size=hash_size)
        return str(ahash)
    except Exception:
        return None


def compute_all_hashes(image_source, hash_size: int = HASH_SIZE) -> Dict[str, Optional[str]]:
    """Compute all hash types for an image."""
    return {
        'phash': compute_phash(image_source, hash_size),
        'dhash': compute_dhash(image_source, hash_size),
        'ahash': compute_ahash(image_source, hash_size),
    }


def hash_distance(hash1: str, hash2: str) -> int:
    """
    Compute Hamming distance between two hashes.

    Returns the number of differing bits.
    """
    if not HAS_IMAGEHASH:
        raise ImportError("imagehash required")

    h1 = imagehash.hex_to_hash(hash1)
    h2 = imagehash.hex_to_hash(hash2)
    return h1 - h2


def are_duplicates(
    hash1: str,
    hash2: str,
    threshold: int = DEFAULT_THRESHOLD
) -> bool:
    """Check if two images are duplicates based on hash distance."""
    return hash_distance(hash1, hash2) <= threshold


def _load_image(image_source) -> Image.Image:
    """Load image from various sources."""
    if isinstance(image_source, Image.Image):
        return image_source.convert("RGB")

    if isinstance(image_source, (str, Path)):
        path = str(image_source)

        # URL
        if path.startswith(('http://', 'https://')):
            if not HAS_REQUESTS:
                raise ImportError("requests required for URL loading")
            response = requests.get(path, timeout=30)
            response.raise_for_status()
            return Image.open(BytesIO(response.content)).convert("RGB")

        # Local file
        return Image.open(path).convert("RGB")

    raise ValueError(f"Unsupported image source: {type(image_source)}")


class DuplicateDetector:
    """
    Detect and manage duplicate images using perceptual hashing.

    Usage:
        detector = DuplicateDetector()

        # Add images
        detector.add("img1.jpg", "id1")
        detector.add("img2.jpg", "id2")

        # Check for duplicates
        is_dup, matches = detector.is_duplicate("new_img.jpg")

        # Find all duplicate groups
        groups = detector.find_duplicate_groups()
    """

    def __init__(
        self,
        threshold: int = DEFAULT_THRESHOLD,
        hash_type: str = 'phash'
    ):
        """
        Initialize duplicate detector.

        Args:
            threshold: Maximum hash distance to consider as duplicate
            hash_type: 'phash', 'dhash', or 'ahash'
        """
        if not HAS_IMAGEHASH:
            raise ImportError("imagehash required. Run: pip install imagehash")

        self.threshold = threshold
        self.hash_type = hash_type

        # Storage: hash -> list of image IDs with that hash
        self.hash_index: Dict[str, List[str]] = defaultdict(list)

        # Reverse lookup: image_id -> hash
        self.id_to_hash: Dict[str, str] = {}

    def _compute_hash(self, image_source) -> Optional[str]:
        """Compute hash using configured algorithm."""
        if self.hash_type == 'phash':
            return compute_phash(image_source)
        elif self.hash_type == 'dhash':
            return compute_dhash(image_source)
        elif self.hash_type == 'ahash':
            return compute_ahash(image_source)
        else:
            raise ValueError(f"Unknown hash type: {self.hash_type}")

    def add(self, image_source, image_id: str) -> Optional[str]:
        """
        Add an image to the index.

        Args:
            image_source: Path, URL, or PIL Image
            image_id: Unique identifier for the image

        Returns:
            The computed hash, or None on error
        """
        if image_id in self.id_to_hash:
            return self.id_to_hash[image_id]

        hash_value = self._compute_hash(image_source)
        if hash_value:
            self.hash_index[hash_value].append(image_id)
            self.id_to_hash[image_id] = hash_value

        return hash_value

    def is_duplicate(
        self,
        image_source,
        threshold: int = None
    ) -> Tuple[bool, List[str]]:
        """
        Check if an image is a duplicate of any indexed image.

        Args:
            image_source: Path, URL, or PIL Image
            threshold: Override default threshold

        Returns:
            Tuple of (is_duplicate, list of matching image IDs)
        """
        threshold = threshold if threshold is not None else self.threshold

        hash_value = self._compute_hash(image_source)
        if not hash_value:
            return False, []

        matches = []

        for indexed_hash, image_ids in self.hash_index.items():
            distance = hash_distance(hash_value, indexed_hash)
            if distance <= threshold:
                matches.extend(image_ids)

        return len(matches) > 0, matches

    def find_similar(
        self,
        image_source,
        max_distance: int = None,
        limit: int = 10
    ) -> List[Tuple[str, int]]:
        """
        Find images similar to the given image.

        Args:
            image_source: Path, URL, or PIL Image
            max_distance: Maximum hash distance to include
            limit: Maximum number of results

        Returns:
            List of (image_id, distance) tuples, sorted by distance
        """
        max_distance = max_distance if max_distance is not None else self.threshold * 2

        hash_value = self._compute_hash(image_source)
        if not hash_value:
            return []

        results = []

        for indexed_hash, image_ids in self.hash_index.items():
            distance = hash_distance(hash_value, indexed_hash)
            if distance <= max_distance:
                for image_id in image_ids:
                    results.append((image_id, distance))

        # Sort by distance and limit
        results.sort(key=lambda x: x[1])
        return results[:limit]

    def find_duplicate_groups(self) -> List[List[str]]:
        """
        Find all groups of duplicate images.

        Returns:
            List of lists, where each inner list contains IDs of duplicate images
        """
        # Build a graph of similar images
        from collections import deque

        visited = set()
        groups = []

        for start_hash in self.hash_index:
            if start_hash in visited:
                continue

            # BFS to find all connected hashes
            group_hashes = set()
            queue = deque([start_hash])

            while queue:
                current_hash = queue.popleft()
                if current_hash in group_hashes:
                    continue

                group_hashes.add(current_hash)
                visited.add(current_hash)

                # Find similar hashes
                for other_hash in self.hash_index:
                    if other_hash not in group_hashes:
                        distance = hash_distance(current_hash, other_hash)
                        if distance <= self.threshold:
                            queue.append(other_hash)

            # Collect all image IDs in this group
            group_ids = []
            for h in group_hashes:
                group_ids.extend(self.hash_index[h])

            if len(group_ids) > 1:
                groups.append(group_ids)

        return groups

    def remove(self, image_id: str):
        """Remove an image from the index."""
        if image_id in self.id_to_hash:
            hash_value = self.id_to_hash[image_id]
            self.hash_index[hash_value].remove(image_id)
            if not self.hash_index[hash_value]:
                del self.hash_index[hash_value]
            del self.id_to_hash[image_id]

    def clear(self):
        """Clear all indexed images."""
        self.hash_index.clear()
        self.id_to_hash.clear()

    def stats(self) -> Dict:
        """Get index statistics."""
        return {
            'total_images': len(self.id_to_hash),
            'unique_hashes': len(self.hash_index),
            'hash_type': self.hash_type,
            'threshold': self.threshold,
        }


# Database integration helpers

def add_hash_column_to_db():
    """Add phash column to images table if not exists."""
    import sqlite3
    from .database import DB_PATH

    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("ALTER TABLE images ADD COLUMN phash TEXT")
        conn.commit()
        print("Added phash column to images table")
    except sqlite3.OperationalError as e:
        if "duplicate column" in str(e).lower():
            pass  # Column already exists
        else:
            raise
    finally:
        conn.close()


def compute_hashes_for_existing(batch_size: int = 100) -> int:
    """
    Compute and store hashes for all images without hashes.

    Returns number of images processed.
    """
    from .database import get_connection

    add_hash_column_to_db()

    processed = 0

    with get_connection() as conn:
        # Get images without hashes that have local paths
        cursor = conn.execute("""
            SELECT id, local_path, image_url
            FROM images
            WHERE phash IS NULL AND (local_path IS NOT NULL OR image_url IS NOT NULL)
            LIMIT ?
        """, (batch_size,))

        rows = cursor.fetchall()

        for row in rows:
            image_id = row[0]
            local_path = row[1]
            image_url = row[2]

            # Prefer local path if available
            source = local_path if local_path and Path(local_path).exists() else image_url

            if source:
                hash_value = compute_phash(source)
                if hash_value:
                    conn.execute(
                        "UPDATE images SET phash = ? WHERE id = ?",
                        (hash_value, image_id)
                    )
                    processed += 1

    return processed


def find_duplicates_in_db(threshold: int = DEFAULT_THRESHOLD) -> List[List[int]]:
    """
    Find duplicate groups in the database.

    Returns list of lists containing image IDs that are duplicates.
    """
    from .database import get_connection

    detector = DuplicateDetector(threshold=threshold)

    with get_connection() as conn:
        cursor = conn.execute("""
            SELECT id, phash FROM images WHERE phash IS NOT NULL
        """)

        for row in cursor:
            image_id, phash = row
            # Add to detector using the pre-computed hash
            detector.hash_index[phash].append(str(image_id))
            detector.id_to_hash[str(image_id)] = phash

    groups = detector.find_duplicate_groups()

    # Convert IDs back to integers
    return [[int(id_str) for id_str in group] for group in groups]


def mark_duplicates_in_db(keep_best: bool = True) -> int:
    """
    Find duplicates and mark lower-quality ones as rejected.

    Args:
        keep_best: If True, keeps the highest quality image in each group

    Returns:
        Number of images marked as duplicates
    """
    from .database import get_connection, update_image

    groups = find_duplicates_in_db()
    marked = 0

    with get_connection() as conn:
        for group in groups:
            if len(group) < 2:
                continue

            if keep_best:
                # Get quality scores for all images in group
                placeholders = ','.join('?' * len(group))
                cursor = conn.execute(f"""
                    SELECT id, quality_score FROM images
                    WHERE id IN ({placeholders})
                    ORDER BY quality_score DESC NULLS LAST
                """, group)

                rows = cursor.fetchall()

                # Keep the first (highest quality), mark rest as duplicates
                for i, (image_id, _) in enumerate(rows):
                    if i > 0:
                        update_image(image_id, {
                            'status': 'rejected',
                            'notes': f'Duplicate of image {rows[0][0]}'
                        })
                        marked += 1
            else:
                # Mark all but first as duplicates
                for image_id in group[1:]:
                    update_image(image_id, {
                        'status': 'rejected',
                        'notes': f'Duplicate of image {group[0]}'
                    })
                    marked += 1

    return marked

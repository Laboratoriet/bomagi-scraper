"""Base scraper infrastructure for Bomagi."""
import os
import re
import hashlib
import requests
from pathlib import Path
from typing import Optional, List, Dict, Any, Generator
from abc import ABC, abstractmethod
from urllib.parse import urlparse

# Image storage path
IMAGES_DIR = Path(__file__).parent.parent / "images"
IMAGES_DIR.mkdir(parents=True, exist_ok=True)

# Room type keywords for classification
ROOM_KEYWORDS = {
    'living_room': [
        'living room', 'living-room', 'lounge', 'family room', 'sitting room',
        'stue', 'vardagsrum', 'wohnzimmer', 'salon'
    ],
    'kitchen': [
        'kitchen', 'kitchenette', 'cooking', 'culinary',
        'kjøkken', 'kök', 'küche', 'cuisine'
    ],
    'bedroom': [
        'bedroom', 'bed room', 'master bedroom', 'guest room', 'sleeping',
        'soverom', 'sovrum', 'schlafzimmer', 'chambre'
    ],
    'bathroom': [
        'bathroom', 'bath room', 'toilet', 'wc', 'shower', 'ensuite',
        'bad', 'badrum', 'badezimmer', 'salle de bain'
    ],
    'hallway': [
        'hallway', 'hall', 'corridor', 'entrance', 'entryway', 'foyer', 'mudroom',
        'gang', 'hall', 'flur', 'entrée'
    ],
    'dining': [
        'dining room', 'dining-room', 'dining area', 'breakfast nook',
        'spisestue', 'matsal', 'esszimmer', 'salle à manger'
    ],
    'office': [
        'office', 'home office', 'study', 'workspace', 'work from home', 'desk',
        'kontor', 'hemmakontor', 'büro', 'bureau'
    ],
    'outdoor': [
        'outdoor', 'patio', 'terrace', 'balcony', 'garden', 'deck', 'veranda',
        'uteplass', 'terrasse', 'balkong', 'hage'
    ],
}


def classify_room_type(text: str) -> Optional[str]:
    """Classify room type from text (title, description, prompt)."""
    if not text:
        return None

    text_lower = text.lower()

    for room_type, keywords in ROOM_KEYWORDS.items():
        for keyword in keywords:
            if keyword in text_lower:
                return room_type

    return 'other'


def compute_quality_score(
    width: int = 0,
    height: int = 0,
    engagement: int = 0,
    has_prompt: bool = False
) -> float:
    """Compute a quality score from 0-1."""
    score = 0.0

    # Resolution score (0-0.4)
    min_dim = min(width or 0, height or 0)
    if min_dim >= 1080:
        score += 0.4
    elif min_dim >= 720:
        score += 0.3
    elif min_dim >= 480:
        score += 0.2
    elif min_dim > 0:
        score += 0.1

    # Engagement score (0-0.4)
    if engagement >= 1000:
        score += 0.4
    elif engagement >= 500:
        score += 0.3
    elif engagement >= 100:
        score += 0.2
    elif engagement >= 10:
        score += 0.1

    # Has prompt/metadata (0-0.2)
    if has_prompt:
        score += 0.2

    return round(score, 2)


def download_image(url: str, source: str, source_id: str) -> Optional[str]:
    """Download image and return local path."""
    try:
        # Create source subdirectory
        source_dir = IMAGES_DIR / source
        source_dir.mkdir(exist_ok=True)

        # Generate filename from source_id
        ext = Path(urlparse(url).path).suffix or '.jpg'
        if ext.lower() not in ['.jpg', '.jpeg', '.png', '.webp', '.gif']:
            ext = '.jpg'

        # Use hash of source_id for consistent naming
        filename = f"{hashlib.md5(source_id.encode()).hexdigest()[:16]}{ext}"
        filepath = source_dir / filename

        # Skip if already downloaded
        if filepath.exists():
            return str(filepath)

        # Download
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        }
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()

        # Verify it's actually an image
        content_type = response.headers.get('content-type', '')
        if not content_type.startswith('image/'):
            return None

        with open(filepath, 'wb') as f:
            f.write(response.content)

        return str(filepath)

    except Exception as e:
        print(f"    Failed to download {url}: {e}")
        return None


class BaseSource(ABC):
    """Abstract base class for image sources."""

    name: str = "base"
    requires_auth: bool = False

    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}

    @abstractmethod
    def search(self, query: str, room_type: str = None, limit: int = 50) -> Generator[Dict, None, None]:
        """
        Search for images. Yields dicts with:
        - source: str
        - source_id: str
        - source_url: str
        - image_url: str
        - thumbnail_url: str (optional)
        - title: str (optional)
        - description: str (optional)
        - prompt: str (optional)
        - width: int (optional)
        - height: int (optional)
        - engagement: int (optional)
        - style_tags: List[str] (optional)
        """
        pass

    def process_result(self, result: Dict) -> Dict:
        """Post-process a search result with classification and scoring."""
        # Classify room type
        text_for_classification = ' '.join(filter(None, [
            result.get('title', ''),
            result.get('description', ''),
            result.get('prompt', '')
        ]))
        result['room_type'] = result.get('room_type') or classify_room_type(text_for_classification)

        # Compute quality score
        result['quality_score'] = compute_quality_score(
            width=result.get('width', 0),
            height=result.get('height', 0),
            engagement=result.get('engagement', 0),
            has_prompt=bool(result.get('prompt'))
        )

        return result

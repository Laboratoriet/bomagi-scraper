# Bomagi Interior Inspiration Scraper

Multi-source scraper for gathering high-quality interior design images, with CLIP-based room classification, perceptual hash deduplication, and a curation UI.

## Sources

| Source | Type | API | Quality |
|--------|------|-----|---------|
| **Civitai** | AI-generated | Official REST | ⭐⭐⭐⭐⭐ |
| **Lexica** | AI-generated (SD) | Unofficial | ⭐⭐⭐⭐ |
| **Midjourney** | AI-generated | Browser scrape | ⭐⭐⭐⭐⭐ |
| **Pinterest** | Mixed/curated | HAR/Apify/Direct | ⭐⭐⭐⭐⭐ |
| **Finn.no** | Real photos | Browser scrape | ⭐⭐⭐⭐ |

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# For browser-based scraping (Midjourney, Finn.no, Pinterest)
playwright install chromium

# Initialize database
python -c "from scraper import init_db; init_db()"

# Scrape some images
python cli.py scrape civitai "scandinavian interior design" --limit 100

# Run CLIP classification
python cli.py classify

# Find and remove duplicates
python cli.py dedup

# Bulk download approved images
python cli.py download

# Start the curation UI
python cli.py serve
```

## CLI Usage

### Scrape images
```bash
# Basic scrape from AI sources
python cli.py scrape civitai "modern kitchen" --limit 50
python cli.py scrape lexica "cozy bedroom" --room bedroom --limit 30

# Scrape Midjourney showcase
python cli.py scrape midjourney "minimalist living room" --download

# Scrape Finn.no (Norwegian real estate)
python cli.py scrape finn --limit 20

# Scrape Pinterest (using HAR file from your browser)
python cli.py scrape pinterest --har ~/Downloads/pinterest.har --limit 100

# Scrape Pinterest (using Apify - requires token)
python cli.py scrape pinterest_apify "scandinavian interior" --apify-token YOUR_TOKEN
```

### Bulk download
```bash
# Download all approved images
python cli.py download

# Download specific subset
python cli.py download --status approved --room kitchen --workers 8

# Re-download all (including already downloaded)
python cli.py download --redownload
```

### CLIP classification
```bash
# Classify all unclassified images
python cli.py classify

# Re-classify everything (including already classified)
python cli.py classify --reprocess

# Classify only approved images
python cli.py classify --status approved
```

### Deduplication
```bash
# Find and mark duplicates
python cli.py dedup

# Stricter matching (lower threshold = stricter)
python cli.py dedup --threshold 5

# Preview duplicates without marking them
python cli.py dedup --dry-run
```

### View stats
```bash
python cli.py stats
```

### Export curated images
```bash
# Export approved images
python cli.py export approved --output training_data.json

# Export by room type
python cli.py export approved --room kitchen --output kitchens.json
```

### Run web UI
```bash
python cli.py serve --port 8000
```

## Pinterest Scraping

Pinterest is a goldmine for interior inspiration but notoriously hard to scrape. We support three methods:

### 1. HAR File Method (Recommended - most "legal")
1. Open Pinterest in Chrome
2. Open DevTools (F12) → Network tab
3. Browse Pinterest boards/search results you want
4. Right-click in Network tab → "Save all as HAR with content"
5. Run: `python cli.py scrape pinterest --har ~/Downloads/pinterest.har`

### 2. Apify Integration (Paid but reliable)
1. Get an API token from [Apify](https://apify.com/)
2. Run: `python cli.py scrape pinterest_apify "interior design" --apify-token YOUR_TOKEN`

### 3. Direct Scraping (Risky - may get blocked)
```bash
python cli.py scrape pinterest_direct "scandinavian interior" --limit 50
```

## CLIP Classification

Instead of keyword matching, we use OpenAI's CLIP model to visually classify room types:

```python
from scraper.classifier import CLIPClassifier

classifier = CLIPClassifier()

# Classify room type
room_type, confidence = classifier.classify_room("image.jpg")
# -> ('living_room', 0.87)

# Get full classification with styles
result = classifier.classify_full("image.jpg")
# -> {
#     'room_type': 'living_room',
#     'room_confidence': 0.87,
#     'styles': ['scandinavian', 'minimalist', 'modern']
# }
```

## Deduplication

Perceptual hashing detects near-duplicate images even with:
- Different resolutions
- Minor crops
- Compression artifacts
- Color adjustments

```python
from scraper.dedup import DuplicateDetector

detector = DuplicateDetector(threshold=8)

# Add images
detector.add("img1.jpg", "id1")
detector.add("img2.jpg", "id2")

# Check for duplicates
is_dup, matches = detector.is_duplicate("new_image.jpg")

# Find all duplicate groups
groups = detector.find_duplicate_groups()
```

## Architecture

```
bomagi-scraper/
├── scraper/
│   ├── base.py           # Base classes, keyword classification
│   ├── classifier.py     # CLIP-based room/style classification
│   ├── dedup.py          # Perceptual hash deduplication
│   ├── database.py       # SQLite interface
│   └── sources/
│       ├── civitai.py    # Civitai API
│       ├── lexica.py     # Lexica.art API
│       ├── midjourney.py # MJ showcase scraper
│       ├── pinterest.py  # Pinterest (HAR/Apify/Direct)
│       └── finn.py       # Finn.no scraper
├── api/
│   └── server.py         # FastAPI backend
├── web/
│   └── index.html        # React curation UI
├── db/
│   └── schema.sql        # Database schema
├── cli.py                # Command-line interface
└── requirements.txt
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | API info |
| `/stats` | GET | Database statistics |
| `/scrape` | POST | Start scrape job |
| `/scrape/{id}` | GET | Check scrape status |
| `/images` | GET | List images (with filters) |
| `/images/{id}` | PATCH | Approve/reject image |
| `/images/{id}/download` | POST | Download single image |
| `/export` | GET | Export approved images |

## Dependencies

**Core:**
- requests, beautifulsoup4, Pillow

**Browser automation:**
- playwright (run `playwright install chromium`)

**Classification:**
- torch, transformers (for CLIP)

**Deduplication:**
- imagehash

**API server:**
- fastapi, uvicorn, pydantic

## Legal Notes

- **Civitai**: Official API, check their terms for AI training use
- **Lexica**: Public search, standard web scraping considerations
- **Midjourney**: Showcase is public, but ToS may restrict automation
- **Pinterest**: Explicitly prohibits scraping in ToS. HAR method uses your own browsing data. Use responsibly.
- **Finn.no**: No public API, scrape responsibly with delays

For production/commercial use, consider reaching out to sources for licensing agreements.

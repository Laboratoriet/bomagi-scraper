#!/usr/bin/env python3
"""
Bomagi Interior Scraper - CLI Interface

Usage:
    python cli.py scrape civitai "scandinavian interior" --limit 50
    python cli.py scrape lexica "modern kitchen" --room kitchen --limit 30
    python cli.py scrape pinterest --har browsing.har --limit 100
    python cli.py scrape finn --limit 20

    python cli.py stats
    python cli.py export approved --output approved_images.json

    python cli.py download                    # Download all approved images
    python cli.py download --status pending   # Download pending images
    python cli.py download --room kitchen     # Download kitchen images only

    python cli.py classify                    # Run CLIP classification on all images
    python cli.py classify --reprocess        # Re-classify already classified images

    python cli.py dedup                       # Find and mark duplicates
    python cli.py dedup --threshold 5         # Stricter matching

    python cli.py serve
"""

import argparse
import json
import sys
import os
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

from scraper import init_db, get_stats, get_source, SOURCES
from scraper.database import (
    get_images, insert_image, image_exists, update_image,
    get_images_for_download, get_download_stats, bulk_update_status
)
from scraper.base import download_image


def cmd_scrape(args):
    """Run a scrape job."""
    source_name = args.source

    # Handle Pinterest special config
    config = {}
    if 'pinterest' in source_name and args.har:
        config['har_path'] = args.har
    if args.apify_token:
        config['apify_token'] = args.apify_token

    if source_name not in SOURCES:
        print(f"Unknown source: {source_name}")
        print(f"Available sources: {', '.join(SOURCES.keys())}")
        return 1

    print(f"Scraping {source_name} for: {args.query}")
    print(f"  Room type: {args.room or 'all'}")
    print(f"  Limit: {args.limit}")
    print(f"  Download: {args.download}")
    print()

    source = get_source(source_name, config)
    found = 0
    new = 0
    errors = 0

    try:
        for result in source.search(
            query=args.query,
            room_type=args.room,
            limit=args.limit
        ):
            found += 1

            # Process result
            result = source.process_result(result)

            # Check if exists
            if image_exists(result["source"], result["source_id"]):
                print(f"  [{found}] Skip (exists): {result['source_id'][:20]}")
                continue

            # Download if requested
            if args.download:
                local_path = download_image(
                    result["image_url"],
                    result["source"],
                    result["source_id"]
                )
                result["local_path"] = local_path

            # Insert into database
            insert_image(result)
            new += 1

            room = result.get('room_type', '?')
            quality = result.get('quality_score', 0)
            print(f"  [{found}] New: {result['source_id'][:20]} | {room} | q={quality:.2f}")

    except KeyboardInterrupt:
        print("\nInterrupted by user")
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
        errors += 1

    print()
    print(f"Done! Found: {found}, New: {new}, Errors: {errors}")
    return 0


def cmd_stats(args):
    """Show database statistics."""
    stats = get_stats()
    dl_stats = get_download_stats()

    print("=== Bomagi Database Stats ===\n")
    print(f"Total images: {stats['total']}")

    print("\nBy source:")
    for source, count in stats.get('by_source', {}).items():
        print(f"  {source}: {count}")

    print("\nBy room type:")
    for room, count in stats.get('by_room_type', {}).items():
        print(f"  {room}: {count}")

    print("\nBy status:")
    for status, count in stats.get('by_status', {}).items():
        print(f"  {status}: {count}")

    print("\nDownload status:")
    print(f"  Downloaded: {dl_stats['downloaded']}")
    print(f"  Pending: {dl_stats['pending_download']}")
    print(f"  Approved & downloaded: {dl_stats['approved_downloaded']}")
    print(f"  Approved & pending: {dl_stats['approved_pending']}")

    return 0


def cmd_export(args):
    """Export images to JSON."""
    images = get_images(
        status=args.status if args.status != 'all' else None,
        room_type=args.room,
        limit=10000,
        order_by="room_type, quality_score DESC"
    )

    output = {
        "count": len(images),
        "filters": {
            "status": args.status,
            "room_type": args.room
        },
        "images": images
    }

    if args.output:
        with open(args.output, 'w') as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
        print(f"Exported {len(images)} images to {args.output}")
    else:
        print(json.dumps(output, indent=2, ensure_ascii=False))

    return 0


def cmd_download(args):
    """Bulk download images."""
    print("=== Bulk Download ===\n")

    # Get images to download
    images = get_images_for_download(
        status=args.status,
        room_type=args.room,
        source=args.source,
        only_missing=not args.redownload
    )

    if not images:
        print("No images to download.")
        return 0

    print(f"Found {len(images)} images to download")
    print(f"  Status filter: {args.status or 'all'}")
    print(f"  Room filter: {args.room or 'all'}")
    print(f"  Parallel workers: {args.workers}")
    print()

    downloaded = 0
    failed = 0

    def download_one(img):
        """Download a single image."""
        local_path = download_image(
            img['image_url'],
            img['source'],
            img['source_id']
        )
        return img['id'], local_path

    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {executor.submit(download_one, img): img for img in images}

        for future in as_completed(futures):
            img = futures[future]
            try:
                image_id, local_path = future.result()
                if local_path:
                    update_image(image_id, {'local_path': local_path})
                    downloaded += 1
                    print(f"  [{downloaded}/{len(images)}] Downloaded: {img['source_id'][:20]}")
                else:
                    failed += 1
                    print(f"  [FAILED] {img['source_id'][:20]}")
            except Exception as e:
                failed += 1
                print(f"  [ERROR] {img['source_id'][:20]}: {e}")

    print()
    print(f"Done! Downloaded: {downloaded}, Failed: {failed}")
    return 0


def cmd_classify(args):
    """Run CLIP classification on images."""
    print("=== CLIP Room Classification ===\n")

    try:
        from scraper.classifier import get_classifier, HAS_CLIP
    except ImportError as e:
        print(f"Error importing classifier: {e}")
        print("Install dependencies: pip install torch transformers Pillow")
        return 1

    if not HAS_CLIP:
        print("CLIP dependencies not installed.")
        print("Run: pip install torch transformers Pillow")
        return 1

    # Get images to classify
    images = get_images(
        status=args.status if args.status else None,
        limit=10000
    )

    # Filter to only unclassified unless --reprocess
    if not args.reprocess:
        images = [img for img in images if not img.get('room_type') or img['room_type'] == 'other']

    if not images:
        print("No images to classify.")
        return 0

    print(f"Found {len(images)} images to classify")
    print("Loading CLIP model...")

    classifier = get_classifier()
    classified = 0
    failed = 0

    for img in images:
        try:
            # Use local path if available, otherwise URL
            source = img.get('local_path') or img.get('image_url')
            if not source:
                continue

            result = classifier.classify_full(source)
            room_type = result.get('room_type')
            styles = result.get('styles', [])

            if room_type:
                update_image(img['id'], {
                    'room_type': room_type,
                    'style_tags': json.dumps(styles) if styles else None
                })
                classified += 1
                print(f"  [{classified}/{len(images)}] {img['source_id'][:15]}: {room_type} | {', '.join(styles[:2])}")

        except Exception as e:
            failed += 1
            print(f"  [ERROR] {img['source_id'][:15]}: {e}")

    print()
    print(f"Done! Classified: {classified}, Failed: {failed}")
    return 0


def cmd_dedup(args):
    """Find and mark duplicate images."""
    print("=== Duplicate Detection ===\n")

    try:
        from scraper.dedup import (
            compute_hashes_for_existing,
            find_duplicates_in_db,
            mark_duplicates_in_db,
            HAS_IMAGEHASH
        )
    except ImportError as e:
        print(f"Error importing dedup module: {e}")
        print("Install dependencies: pip install Pillow imagehash")
        return 1

    if not HAS_IMAGEHASH:
        print("imagehash not installed.")
        print("Run: pip install imagehash Pillow")
        return 1

    # Step 1: Compute hashes for images that don't have them
    print("Step 1: Computing perceptual hashes...")
    processed = compute_hashes_for_existing(batch_size=args.batch_size)
    print(f"  Computed hashes for {processed} images")

    # Step 2: Find duplicate groups
    print(f"\nStep 2: Finding duplicates (threshold={args.threshold})...")
    groups = find_duplicates_in_db(threshold=args.threshold)
    print(f"  Found {len(groups)} duplicate groups")

    if not groups:
        print("\nNo duplicates found!")
        return 0

    # Show duplicate groups
    print("\nDuplicate groups:")
    for i, group in enumerate(groups[:10]):  # Show first 10
        print(f"  Group {i+1}: {len(group)} images - IDs: {group}")

    if len(groups) > 10:
        print(f"  ... and {len(groups) - 10} more groups")

    # Step 3: Mark duplicates (if not dry run)
    if args.dry_run:
        print("\n[DRY RUN] Would mark duplicates but --dry-run specified")
    else:
        print("\nStep 3: Marking duplicates as rejected...")
        marked = mark_duplicates_in_db(keep_best=True)
        print(f"  Marked {marked} images as duplicates")

    return 0


def cmd_serve(args):
    """Start the API server."""
    try:
        import uvicorn
        from api.server import app

        print(f"Starting Bomagi API server on http://localhost:{args.port}")
        print(f"Web UI: Open web/index.html in browser")
        print("\nPress Ctrl+C to stop\n")

        uvicorn.run(app, host="0.0.0.0", port=args.port)
    except ImportError:
        print("uvicorn not installed. Run: pip install uvicorn")
        return 1


def main():
    parser = argparse.ArgumentParser(
        description="Bomagi Interior Inspiration Scraper",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s scrape civitai "scandinavian living room" --limit 100
  %(prog)s scrape pinterest --har ~/Downloads/pinterest.har
  %(prog)s download --status approved --workers 8
  %(prog)s classify --reprocess
  %(prog)s dedup --threshold 5
  %(prog)s serve --port 8000
        """
    )
    subparsers = parser.add_subparsers(dest='command', help='Commands')

    # === Scrape command ===
    scrape_parser = subparsers.add_parser('scrape', help='Scrape images from a source')
    scrape_parser.add_argument('source', choices=list(SOURCES.keys()),
                               help='Source to scrape from')
    scrape_parser.add_argument('query', nargs='?', default='interior design',
                               help='Search query (default: "interior design")')
    scrape_parser.add_argument('--room', '-r', choices=[
        'living_room', 'kitchen', 'bedroom', 'bathroom',
        'hallway', 'dining', 'office', 'outdoor'
    ], help='Filter by room type')
    scrape_parser.add_argument('--limit', '-l', type=int, default=50,
                               help='Max images to fetch (default: 50)')
    scrape_parser.add_argument('--download', '-d', action='store_true',
                               help='Download images locally')
    scrape_parser.add_argument('--har', help='HAR file path (for Pinterest)')
    scrape_parser.add_argument('--apify-token', help='Apify API token (for Pinterest)')

    # === Stats command ===
    subparsers.add_parser('stats', help='Show database statistics')

    # === Export command ===
    export_parser = subparsers.add_parser('export', help='Export images to JSON')
    export_parser.add_argument('status', nargs='?', default='approved',
                               choices=['all', 'pending', 'approved', 'rejected'],
                               help='Filter by status (default: approved)')
    export_parser.add_argument('--room', '-r', help='Filter by room type')
    export_parser.add_argument('--output', '-o', help='Output file path')

    # === Download command ===
    download_parser = subparsers.add_parser('download', help='Bulk download images')
    download_parser.add_argument('--status', '-s', default='approved',
                                 choices=['all', 'pending', 'approved', 'rejected'],
                                 help='Filter by status (default: approved)')
    download_parser.add_argument('--room', '-r', help='Filter by room type')
    download_parser.add_argument('--source', help='Filter by source')
    download_parser.add_argument('--workers', '-w', type=int, default=4,
                                 help='Parallel download workers (default: 4)')
    download_parser.add_argument('--redownload', action='store_true',
                                 help='Re-download already downloaded images')

    # === Classify command ===
    classify_parser = subparsers.add_parser('classify', help='Run CLIP room classification')
    classify_parser.add_argument('--status', '-s',
                                 choices=['all', 'pending', 'approved', 'rejected'],
                                 help='Filter by status')
    classify_parser.add_argument('--reprocess', action='store_true',
                                 help='Re-classify already classified images')

    # === Dedup command ===
    dedup_parser = subparsers.add_parser('dedup', help='Find and mark duplicate images')
    dedup_parser.add_argument('--threshold', '-t', type=int, default=8,
                              help='Hash distance threshold (lower=stricter, default: 8)')
    dedup_parser.add_argument('--batch-size', '-b', type=int, default=500,
                              help='Batch size for hash computation (default: 500)')
    dedup_parser.add_argument('--dry-run', action='store_true',
                              help="Show duplicates but don't mark them")

    # === Serve command ===
    serve_parser = subparsers.add_parser('serve', help='Start the API server')
    serve_parser.add_argument('--port', '-p', type=int, default=8000,
                              help='Port to run on (default: 8000)')

    args = parser.parse_args()

    # Initialize database
    init_db()

    if args.command == 'scrape':
        return cmd_scrape(args)
    elif args.command == 'stats':
        return cmd_stats(args)
    elif args.command == 'export':
        return cmd_export(args)
    elif args.command == 'download':
        return cmd_download(args)
    elif args.command == 'classify':
        return cmd_classify(args)
    elif args.command == 'dedup':
        return cmd_dedup(args)
    elif args.command == 'serve':
        return cmd_serve(args)
    else:
        parser.print_help()
        return 0


if __name__ == '__main__':
    sys.exit(main())

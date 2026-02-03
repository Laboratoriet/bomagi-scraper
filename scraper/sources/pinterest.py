"""
Pinterest source adapter - Multiple methods for scraping Pinterest.

Methods:
1. HAR File Import - Parse your browser's HAR export (legal, uses your own data)
2. Apify Integration - Use Apify's Pinterest scraper API (paid, but reliable)
3. Direct Scraping - Playwright-based (risky, may get blocked)
"""

import json
import re
import os
from typing import Generator, Dict, Any, Optional, List
from pathlib import Path

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

try:
    from playwright.sync_api import sync_playwright
    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False

from ..base import BaseSource


class PinterestHARSource(BaseSource):
    """
    Pinterest source using HAR file import.

    How to use:
    1. Open Pinterest in Chrome/Firefox
    2. Open DevTools (F12) > Network tab
    3. Browse Pinterest boards/search results you want
    4. Right-click in Network tab > "Save all as HAR"
    5. Pass the HAR file path to this source

    This is the most "legal" method since you're using your own browsing data.
    """

    name = "pinterest_har"
    requires_auth = False

    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)
        self.har_path = config.get('har_path') if config else None

    def search(
        self,
        query: str = None,
        room_type: str = None,
        limit: int = 50,
        har_path: str = None
    ) -> Generator[Dict, None, None]:
        """
        Extract Pinterest images from a HAR file.
        The query parameter is ignored - we extract all images from the HAR.
        """
        har_file = har_path or self.har_path
        if not har_file or not Path(har_file).exists():
            print(f"HAR file not found: {har_file}")
            print("To create a HAR file:")
            print("  1. Open Pinterest in Chrome")
            print("  2. Open DevTools (F12) > Network tab")
            print("  3. Browse boards/search results")
            print("  4. Right-click > 'Save all as HAR with content'")
            return

        print(f"  Parsing HAR file: {har_file}")

        try:
            with open(har_file, 'r', encoding='utf-8') as f:
                har_data = json.load(f)
        except Exception as e:
            print(f"  Error reading HAR file: {e}")
            return

        entries = har_data.get('log', {}).get('entries', [])
        found = 0
        seen_ids = set()

        for entry in entries:
            if found >= limit:
                break

            request = entry.get('request', {})
            response = entry.get('response', {})
            url = request.get('url', '')

            # Look for Pinterest API responses containing pin data
            if 'pinterest.com' in url and response.get('status') == 200:
                content = response.get('content', {})
                mime_type = content.get('mimeType', '')

                if 'json' in mime_type:
                    text = content.get('text', '')
                    if text:
                        pins = self._extract_pins_from_json(text)
                        for pin in pins:
                            if found >= limit:
                                break
                            if pin['source_id'] not in seen_ids:
                                seen_ids.add(pin['source_id'])
                                found += 1
                                yield pin

    def _extract_pins_from_json(self, json_text: str) -> List[Dict]:
        """Extract pin data from Pinterest API JSON response."""
        pins = []

        try:
            data = json.loads(json_text)
        except json.JSONDecodeError:
            return pins

        # Pinterest API responses have various structures
        # Look for common patterns containing pin data
        self._find_pins_recursive(data, pins)

        return pins

    def _find_pins_recursive(self, obj: Any, pins: List[Dict], depth: int = 0):
        """Recursively search for pin objects in nested JSON."""
        if depth > 10:  # Prevent infinite recursion
            return

        if isinstance(obj, dict):
            # Check if this looks like a pin object
            if 'id' in obj and 'images' in obj:
                pin = self._parse_pin(obj)
                if pin:
                    pins.append(pin)
            elif 'id' in obj and 'image_signature' in obj:
                pin = self._parse_pin(obj)
                if pin:
                    pins.append(pin)
            else:
                # Recurse into dict values
                for value in obj.values():
                    self._find_pins_recursive(value, pins, depth + 1)

        elif isinstance(obj, list):
            for item in obj:
                self._find_pins_recursive(item, pins, depth + 1)

    def _parse_pin(self, pin_data: Dict) -> Optional[Dict]:
        """Parse a Pinterest pin object into our format."""
        try:
            pin_id = str(pin_data.get('id', ''))
            if not pin_id:
                return None

            # Get image URL - Pinterest has multiple image sizes
            images = pin_data.get('images', {})
            image_url = None
            thumbnail_url = None

            # Try to get the largest image
            for size_key in ['orig', '736x', '564x', '474x', '236x']:
                if size_key in images:
                    img_data = images[size_key]
                    if isinstance(img_data, dict):
                        image_url = img_data.get('url')
                        break
                    elif isinstance(img_data, str):
                        image_url = img_data
                        break

            # Alternative: construct URL from image_signature
            if not image_url and 'image_signature' in pin_data:
                sig = pin_data['image_signature']
                image_url = f"https://i.pinimg.com/originals/{sig[:2]}/{sig[2:4]}/{sig[4:6]}/{sig}.jpg"

            if not image_url:
                return None

            # Get thumbnail
            for size_key in ['236x', '474x']:
                if size_key in images:
                    img_data = images[size_key]
                    if isinstance(img_data, dict):
                        thumbnail_url = img_data.get('url')
                        break

            # Get description/title
            description = pin_data.get('description', '') or pin_data.get('title', '')
            grid_title = pin_data.get('grid_title', '')

            # Get board info
            board = pin_data.get('board', {})
            board_name = board.get('name', '') if isinstance(board, dict) else ''

            # Get engagement
            repin_count = pin_data.get('repin_count', 0) or 0
            like_count = pin_data.get('like_count', 0) or 0
            comment_count = pin_data.get('comment_count', 0) or 0
            engagement = repin_count + like_count + comment_count

            return {
                "source": "pinterest",
                "source_id": pin_id,
                "source_url": f"https://pinterest.com/pin/{pin_id}/",
                "image_url": image_url,
                "thumbnail_url": thumbnail_url or image_url,
                "title": grid_title or board_name,
                "description": description[:500] if description else None,
                "prompt": None,  # Real photos, no prompt
                "width": 0,  # Not always available
                "height": 0,
                "engagement": engagement,
                "style_tags": None,
            }

        except Exception as e:
            return None


class PinterestApifySource(BaseSource):
    """
    Pinterest source using Apify's Pinterest Scraper.

    Requires an Apify API token. Get one at: https://apify.com/

    More reliable than direct scraping, handles rate limits and blocks.
    """

    name = "pinterest_apify"
    requires_auth = True

    APIFY_ACTOR = "alexey/pinterest-crawler"
    APIFY_API_URL = "https://api.apify.com/v2"

    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)
        self.api_token = (config or {}).get('apify_token') or os.environ.get('APIFY_TOKEN')

    def search(
        self,
        query: str = "scandinavian interior design",
        room_type: str = None,
        limit: int = 50
    ) -> Generator[Dict, None, None]:
        """
        Search Pinterest via Apify actor.
        """
        if not self.api_token:
            print("Apify token not set. Set APIFY_TOKEN env var or pass apify_token in config.")
            return

        if not HAS_REQUESTS:
            print("requests library not installed")
            return

        # Build search query
        search_query = query
        if room_type:
            search_query = f"{room_type.replace('_', ' ')} {query}"

        # Start the actor run
        run_input = {
            "search": search_query,
            "maxPins": limit,
            "proxyConfiguration": {
                "useApifyProxy": True
            }
        }

        try:
            # Start actor
            print(f"  Starting Apify Pinterest scraper for: {search_query}")
            response = requests.post(
                f"{self.APIFY_API_URL}/acts/{self.APIFY_ACTOR}/runs",
                params={"token": self.api_token},
                json=run_input,
                timeout=30
            )
            response.raise_for_status()
            run_data = response.json()
            run_id = run_data['data']['id']

            # Wait for completion (poll)
            import time
            while True:
                status_response = requests.get(
                    f"{self.APIFY_API_URL}/actor-runs/{run_id}",
                    params={"token": self.api_token},
                    timeout=30
                )
                status_data = status_response.json()
                status = status_data['data']['status']

                if status == 'SUCCEEDED':
                    break
                elif status in ['FAILED', 'ABORTED', 'TIMED-OUT']:
                    print(f"  Apify run failed with status: {status}")
                    return

                time.sleep(5)

            # Get results
            dataset_id = status_data['data']['defaultDatasetId']
            results_response = requests.get(
                f"{self.APIFY_API_URL}/datasets/{dataset_id}/items",
                params={"token": self.api_token, "format": "json"},
                timeout=60
            )
            results = results_response.json()

            # Yield results
            for item in results:
                pin = self._parse_apify_result(item)
                if pin:
                    yield pin

        except Exception as e:
            print(f"  Apify error: {e}")

    def _parse_apify_result(self, item: Dict) -> Optional[Dict]:
        """Parse Apify scraper result into our format."""
        try:
            pin_id = str(item.get('id', ''))
            if not pin_id:
                return None

            image_url = item.get('image') or item.get('images', {}).get('orig', {}).get('url')
            if not image_url:
                return None

            return {
                "source": "pinterest",
                "source_id": pin_id,
                "source_url": item.get('url') or f"https://pinterest.com/pin/{pin_id}/",
                "image_url": image_url,
                "thumbnail_url": item.get('images', {}).get('236x', {}).get('url') or image_url,
                "title": item.get('title'),
                "description": item.get('description'),
                "prompt": None,
                "width": item.get('images', {}).get('orig', {}).get('width', 0),
                "height": item.get('images', {}).get('orig', {}).get('height', 0),
                "engagement": (item.get('saves', 0) or 0) + (item.get('comments', 0) or 0),
                "style_tags": None,
            }
        except Exception:
            return None


class PinterestDirectSource(BaseSource):
    """
    Direct Pinterest scraping using Playwright.

    WARNING: This may violate Pinterest's ToS and could get your IP blocked.
    Use at your own risk. Consider using HAR or Apify methods instead.
    """

    name = "pinterest_direct"
    requires_auth = False

    def search(
        self,
        query: str = "scandinavian interior design",
        room_type: str = None,
        limit: int = 50
    ) -> Generator[Dict, None, None]:
        """
        Directly scrape Pinterest search results.
        """
        if not HAS_PLAYWRIGHT:
            print("Playwright not installed. Run: pip install playwright && playwright install chromium")
            return

        search_query = query
        if room_type:
            search_query = f"{room_type.replace('_', ' ')} {query}"

        search_url = f"https://www.pinterest.com/search/pins/?q={search_query.replace(' ', '%20')}"

        found = 0

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
            )
            page = context.new_page()

            try:
                print(f"  Loading Pinterest search: {search_query}")
                page.goto(search_url, wait_until='networkidle', timeout=30000)
                page.wait_for_timeout(3000)

                # Scroll to load more pins
                scroll_count = 0
                max_scrolls = limit // 20  # Roughly 20 pins per scroll

                seen_ids = set()

                while found < limit and scroll_count < max_scrolls:
                    # Extract pins from current view
                    pins_data = page.evaluate('''() => {
                        const pins = [];
                        document.querySelectorAll('[data-test-id="pin"]').forEach(el => {
                            const link = el.querySelector('a[href*="/pin/"]');
                            const img = el.querySelector('img');

                            if (link && img) {
                                const href = link.getAttribute('href');
                                const idMatch = href.match(/\\/pin\\/(\\d+)/);

                                if (idMatch) {
                                    pins.push({
                                        id: idMatch[1],
                                        url: img.src,
                                        alt: img.alt || ''
                                    });
                                }
                            }
                        });
                        return pins;
                    }''')

                    for pin in pins_data:
                        if found >= limit:
                            break
                        if pin['id'] not in seen_ids:
                            seen_ids.add(pin['id'])

                            # Upgrade to high-res URL
                            image_url = pin['url']
                            if 'pinimg.com' in image_url:
                                # Replace size indicator with 'originals'
                                image_url = re.sub(
                                    r'/\d+x/',
                                    '/originals/',
                                    image_url
                                )

                            result = {
                                "source": "pinterest",
                                "source_id": pin['id'],
                                "source_url": f"https://pinterest.com/pin/{pin['id']}/",
                                "image_url": image_url,
                                "thumbnail_url": pin['url'],
                                "title": None,
                                "description": pin['alt'],
                                "prompt": None,
                                "width": 0,
                                "height": 0,
                                "engagement": 0,
                                "style_tags": None,
                            }
                            found += 1
                            yield result

                    # Scroll down
                    page.evaluate('window.scrollBy(0, window.innerHeight * 2)')
                    page.wait_for_timeout(2000)
                    scroll_count += 1

            except Exception as e:
                print(f"  Pinterest scrape error: {e}")
            finally:
                browser.close()


# Convenience alias - use HAR method by default
class PinterestSource(PinterestHARSource):
    """Default Pinterest source - uses HAR file import method."""
    name = "pinterest"

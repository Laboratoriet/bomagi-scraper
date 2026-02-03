"""Finn.no source adapter - Norwegian real estate listings."""
import re
from typing import Generator, Dict, Any, Optional, List
from urllib.parse import urljoin

try:
    from playwright.sync_api import sync_playwright
    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False

from bs4 import BeautifulSoup
from ..base import BaseSource


class FinnSource(BaseSource):
    """
    Finn.no real estate image scraper.
    Targets high-quality interior photos from popular listings.
    """

    name = "finn"
    requires_auth = False

    BASE_URL = "https://www.finn.no"
    SEARCH_URL = "https://www.finn.no/realestate/homes/search.html"

    # Room type detection from Norwegian image alt texts
    ROOM_PATTERNS = {
        'living_room': ['stue', 'stua', 'living', 'oppholdsrom'],
        'kitchen': ['kjøkken', 'kjøkkenet', 'kitchen'],
        'bedroom': ['soverom', 'soverommet', 'bedroom', 'master'],
        'bathroom': ['bad', 'badet', 'bathroom', 'wc', 'toalett'],
        'hallway': ['gang', 'gangen', 'entre', 'entré', 'hall'],
        'dining': ['spisestue', 'spiseplass', 'dining'],
        'outdoor': ['balkong', 'terrasse', 'uteplass', 'hage', 'veranda'],
    }

    def search(
        self,
        query: str = None,
        room_type: str = None,
        limit: int = 50,
        sort: str = "PUBLISHED_DESC",  # Most recent
        min_price: int = None,
        location: str = None
    ) -> Generator[Dict, None, None]:
        """
        Search Finn.no for interior images.
        Scrapes listing pages and extracts high-quality photos.
        """
        if not HAS_PLAYWRIGHT:
            print("Playwright not installed. Run: pip install playwright && playwright install chromium")
            return

        found = 0
        page_num = 1

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
            )
            page = context.new_page()

            try:
                while found < limit:
                    # Build search URL
                    params = [f"sort={sort}", f"page={page_num}"]
                    if location:
                        params.append(f"location={location}")
                    if min_price:
                        params.append(f"price_from={min_price}")

                    search_url = f"{self.SEARCH_URL}?{'&'.join(params)}"
                    print(f"  Searching Finn.no page {page_num}...")

                    page.goto(search_url, wait_until='networkidle', timeout=30000)
                    page.wait_for_timeout(2000)

                    # Get listing URLs from search results
                    listing_urls = self._extract_listing_urls(page)

                    if not listing_urls:
                        print("  No more listings found")
                        break

                    # Process each listing
                    for listing_url in listing_urls:
                        if found >= limit:
                            break

                        try:
                            images = self._scrape_listing(page, listing_url, room_type)
                            for img in images:
                                if found >= limit:
                                    break
                                found += 1
                                yield img

                        except Exception as e:
                            print(f"  Error scraping listing: {e}")
                            continue

                    page_num += 1

            except Exception as e:
                print(f"Finn.no scrape error: {e}")
            finally:
                browser.close()

    def _extract_listing_urls(self, page) -> List[str]:
        """Extract listing URLs from search results page."""
        try:
            urls = page.evaluate('''() => {
                const links = [];
                // Finn.no listing links
                document.querySelectorAll('a[href*="/realestate/homes/ad.html"]').forEach(a => {
                    if (a.href && !links.includes(a.href)) {
                        links.push(a.href);
                    }
                });
                return links.slice(0, 10);  // Limit per page
            }''')
            return urls or []
        except Exception:
            return []

    def _scrape_listing(self, page, url: str, filter_room: str = None) -> List[Dict]:
        """Scrape images from a single listing page."""
        images = []

        try:
            page.goto(url, wait_until='networkidle', timeout=30000)
            page.wait_for_timeout(2000)

            # Click to open image gallery if available
            try:
                gallery_button = page.query_selector('[class*="gallery"], [class*="image-viewer"]')
                if gallery_button:
                    gallery_button.click()
                    page.wait_for_timeout(1000)
            except Exception:
                pass

            # Extract FINN code for unique ID
            finn_code = None
            finn_match = re.search(r'finnkode[=:]?\s*(\d+)', page.content(), re.IGNORECASE)
            if finn_match:
                finn_code = finn_match.group(1)
            else:
                # Try from URL
                url_match = re.search(r'finnkode=(\d+)', url)
                if url_match:
                    finn_code = url_match.group(1)

            # Get address for context
            address = self._extract_address(page)

            # Extract all images
            image_data = page.evaluate('''() => {
                const images = [];
                const seen = new Set();

                // Main gallery images
                document.querySelectorAll('img').forEach(img => {
                    let src = img.src || img.dataset.src || img.dataset.lazySrc;
                    if (!src) return;

                    // Skip tiny images and icons
                    if (img.width && img.width < 200) return;
                    if (img.height && img.height < 200) return;

                    // Skip non-content images
                    if (src.includes('logo') || src.includes('icon') || src.includes('avatar')) return;

                    // Get highest resolution version
                    // Finn.no uses mediatjener with size params
                    if (src.includes('mediatjener')) {
                        src = src.replace(/\\/\\d+$/, '/2400');  // Request large size
                    }

                    if (seen.has(src)) return;
                    seen.add(src);

                    images.push({
                        url: src,
                        alt: img.alt || '',
                        width: img.naturalWidth || 0,
                        height: img.naturalHeight || 0
                    });
                });

                // Also check for background images in gallery
                document.querySelectorAll('[style*="background-image"]').forEach(el => {
                    const style = el.style.backgroundImage;
                    const match = style.match(/url\\(["\']?([^"\'\\)]+)["\']?\\)/);
                    if (match && match[1] && !seen.has(match[1])) {
                        seen.add(match[1]);
                        images.push({
                            url: match[1],
                            alt: '',
                            width: 0,
                            height: 0
                        });
                    }
                });

                return images;
            }''')

            # Process each image
            for idx, img in enumerate(image_data or []):
                img_url = img.get('url', '')
                if not img_url or not self._is_interior_image(img_url):
                    continue

                alt_text = img.get('alt', '')

                # Classify room type from alt text
                room_type = self._classify_room(alt_text)

                # Skip if filtering by room and doesn't match
                if filter_room and room_type != filter_room:
                    continue

                source_id = f"{finn_code}_{idx}" if finn_code else f"finn_{hash(img_url)}"

                images.append({
                    "source": self.name,
                    "source_id": source_id,
                    "source_url": url,
                    "image_url": img_url,
                    "thumbnail_url": img_url.replace('/2400', '/800') if '/2400' in img_url else img_url,
                    "title": address,
                    "description": alt_text,
                    "prompt": None,  # Real photos, no prompt
                    "width": img.get('width', 0),
                    "height": img.get('height', 0),
                    "engagement": 0,  # Could extract view count
                    "room_type": room_type,
                    "style_tags": ["norwegian", "real"],
                })

        except Exception as e:
            print(f"  Error processing listing {url}: {e}")

        return images

    def _extract_address(self, page) -> Optional[str]:
        """Extract address from listing page."""
        try:
            # Try common address patterns
            address = page.evaluate('''() => {
                // Look for address in heading or specific elements
                const h1 = document.querySelector('h1');
                if (h1) return h1.textContent.trim();

                const addr = document.querySelector('[class*="address"], [data-testid*="address"]');
                if (addr) return addr.textContent.trim();

                return null;
            }''')
            return address
        except Exception:
            return None

    def _classify_room(self, text: str) -> Optional[str]:
        """Classify room type from Norwegian text."""
        if not text:
            return None

        text_lower = text.lower()
        for room_type, keywords in self.ROOM_PATTERNS.items():
            for keyword in keywords:
                if keyword in text_lower:
                    return room_type

        return 'other'

    def _is_interior_image(self, url: str) -> bool:
        """Check if URL is likely an interior photo (not floor plan, map, etc.)."""
        skip_patterns = [
            'floorplan', 'plantegning', 'map', 'kart', 'logo',
            'agent', 'megler', 'avatar', 'icon', 'thumb'
        ]
        url_lower = url.lower()
        return not any(pattern in url_lower for pattern in skip_patterns)

"""Midjourney showcase scraper - Browser automation."""
import re
import json
from typing import Generator, Dict, Any, Optional

try:
    from playwright.sync_api import sync_playwright
    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False

from ..base import BaseSource


class MidjourneySource(BaseSource):
    """
    Midjourney showcase/explore scraper.
    Uses Playwright for browser automation since there's no public API.

    Note: Midjourney's showcase is publicly accessible, but their ToS
    may restrict automated access. Use responsibly.
    """

    name = "midjourney"
    requires_auth = False  # Showcase is public

    SHOWCASE_URL = "https://www.midjourney.com/showcase"
    EXPLORE_URL = "https://www.midjourney.com/explore"  # Requires login

    def search(
        self,
        query: str = "interior design",
        room_type: str = None,
        limit: int = 50
    ) -> Generator[Dict, None, None]:
        """
        Scrape Midjourney showcase for interior images.
        Since there's no search on showcase, we scrape and filter locally.
        """
        if not HAS_PLAYWRIGHT:
            print("Playwright not installed. Run: pip install playwright && playwright install chromium")
            return

        # Build filter terms
        filter_terms = ["interior", "room", "design"]
        if query:
            filter_terms.extend(query.lower().split())
        if room_type:
            filter_terms.append(room_type.replace('_', ' '))

        found = 0

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
            )
            page = context.new_page()

            try:
                print(f"  Loading Midjourney showcase...")
                page.goto(self.SHOWCASE_URL, wait_until='networkidle', timeout=30000)
                page.wait_for_timeout(3000)

                # Scroll to load more images
                scroll_count = 0
                max_scrolls = 10

                while found < limit and scroll_count < max_scrolls:
                    # Extract visible images
                    images = self._extract_images_from_page(page)

                    for img_data in images:
                        if found >= limit:
                            break

                        # Filter for interior-related images
                        prompt = (img_data.get('prompt') or '').lower()
                        if any(term in prompt for term in filter_terms):
                            result = self._parse_image(img_data)
                            if result:
                                found += 1
                                yield result

                    # Scroll down for more
                    page.evaluate('window.scrollBy(0, window.innerHeight)')
                    page.wait_for_timeout(2000)
                    scroll_count += 1

            except Exception as e:
                print(f"Midjourney scrape error: {e}")
            finally:
                browser.close()

    def _extract_images_from_page(self, page) -> list:
        """Extract image data from current page state."""
        try:
            # Midjourney uses a specific data structure in their React app
            # Try to extract from __NEXT_DATA__ or visible elements

            # Method 1: Try to get from page's JavaScript state
            data = page.evaluate('''() => {
                const images = [];

                // Look for image elements with data attributes
                document.querySelectorAll('img[src*="cdn.midjourney.com"]').forEach(img => {
                    const src = img.src;
                    const alt = img.alt || '';

                    // Try to find parent with more data
                    let parent = img.closest('a, div[class*="image"], div[class*="card"]');
                    let prompt = alt;

                    // Check for prompt in nearby elements
                    if (parent) {
                        const promptEl = parent.querySelector('[class*="prompt"], p, span');
                        if (promptEl) {
                            prompt = promptEl.textContent || alt;
                        }
                    }

                    // Extract ID from URL
                    const idMatch = src.match(/([a-f0-9-]{36})/i);
                    const id = idMatch ? idMatch[1] : null;

                    if (id && src) {
                        images.push({
                            id: id,
                            url: src,
                            prompt: prompt,
                            width: img.naturalWidth || 0,
                            height: img.naturalHeight || 0
                        });
                    }
                });

                return images;
            }''')

            return data or []

        except Exception as e:
            print(f"Error extracting images: {e}")
            return []

    def _parse_image(self, item: Dict) -> Optional[Dict[str, Any]]:
        """Parse extracted image data into our format."""
        try:
            image_id = item.get("id", "")
            if not image_id:
                return None

            image_url = item.get("url", "")
            if not image_url:
                return None

            prompt = item.get("prompt", "")

            # Extract style tags
            tags = []
            if prompt:
                style_words = [
                    "minimalist", "scandinavian", "modern", "cozy", "rustic",
                    "industrial", "bohemian", "contemporary", "traditional",
                    "mid-century", "art deco", "japanese", "nordic",
                    "warm lighting", "natural light", "architectural"
                ]
                prompt_lower = prompt.lower()
                tags = [w for w in style_words if w in prompt_lower]

            return {
                "source": self.name,
                "source_id": image_id,
                "source_url": f"https://www.midjourney.com/jobs/{image_id}",
                "image_url": image_url,
                "thumbnail_url": image_url,
                "title": None,
                "description": None,
                "prompt": prompt[:2000] if prompt else None,
                "width": item.get("width", 0),
                "height": item.get("height", 0),
                "engagement": 0,  # Not available from showcase
                "style_tags": tags if tags else None,
            }

        except Exception as e:
            print(f"Error parsing Midjourney item: {e}")
            return None


class MidjourneyCommunitySource(BaseSource):
    """
    Alternative: Scrape Midjourney community showcase feeds.
    These are curated collections that are publicly visible.
    """

    name = "midjourney_community"

    def search(self, query: str = "interior", room_type: str = None, limit: int = 50):
        """Placeholder for community feed scraping."""
        # Could implement scraping from:
        # - https://www.midjourney.com/showcase/recent/
        # - https://www.midjourney.com/showcase/top/
        # - Discord channel archives
        pass

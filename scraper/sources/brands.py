"""
Scandinavian furniture brand scrapers.
High-quality, curated interior photography from real brands.
"""

import re
import time
from typing import Generator, Dict, Any, List
from urllib.parse import urljoin, urlparse

try:
    from playwright.sync_api import sync_playwright
    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False

from ..base import BaseSource


class BrandScraperBase(BaseSource):
    """Base class for furniture brand scrapers."""

    name = "brand"
    brand_name = "Generic"
    base_url = ""
    inspiration_urls = []  # URLs to scrape for inspiration images

    def _handle_cookie_consent(self, page):
        """Try to accept cookie consent dialogs."""
        consent_selectors = [
            '#CybotCookiebotDialogBodyLevelButtonLevelOptinAllowAll',
            'button:has-text("Accept all")',
            'button:has-text("Accept")',
            'button:has-text("Allow all")',
            'button:has-text("Allow")',
            'button:has-text("I agree")',
            'button:has-text("OK")',
            '[data-testid="cookie-accept"]',
            '[class*="cookie"] button:has-text("Accept")',
            '[class*="consent"] button:has-text("Accept")',
        ]
        for selector in consent_selectors:
            try:
                btn = page.locator(selector)
                if btn.count() > 0:
                    btn.first.click(timeout=3000)
                    page.wait_for_timeout(1000)
                    return True
            except:
                continue
        return False

    def search(
        self,
        query: str = None,
        room_type: str = None,
        limit: int = 50
    ) -> Generator[Dict, None, None]:
        """Scrape inspiration images from brand website."""
        if not HAS_PLAYWRIGHT:
            print("Playwright required. Run: playwright install chromium")
            return

        found = 0

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            )
            page = context.new_page()

            try:
                for url in self.inspiration_urls:
                    if found >= limit:
                        break

                    print(f"  Scraping {self.brand_name}: {url}")

                    try:
                        page.goto(url, wait_until='domcontentloaded', timeout=30000)
                        page.wait_for_timeout(2000)

                        # Handle cookie consent
                        self._handle_cookie_consent(page)

                        # Scroll to load lazy images
                        for _ in range(5):
                            page.evaluate('window.scrollBy(0, window.innerHeight)')
                            page.wait_for_timeout(800)

                        images = self._extract_images(page, url)

                        for img in images:
                            if found >= limit:
                                break

                            # Filter by room type if specified
                            if room_type and img.get('room_type') != room_type:
                                continue

                            found += 1
                            yield img

                    except Exception as e:
                        print(f"    Error: {e}")
                        continue

            finally:
                browser.close()

    def _extract_images(self, page, source_url: str) -> List[Dict]:
        """Extract images from page. Override in subclasses for custom logic."""
        images = []
        seen = set()

        # Generic image extraction
        img_data = page.evaluate('''() => {
            const images = [];
            document.querySelectorAll('img').forEach(img => {
                let src = img.src || img.dataset.src || img.dataset.lazySrc;
                if (!src) return;

                // Skip tiny images, icons, logos
                const width = img.naturalWidth || img.width || 0;
                const height = img.naturalHeight || img.height || 0;
                if (width < 400 || height < 300) return;

                // Skip common non-content patterns
                const srcLower = src.toLowerCase();
                if (srcLower.includes('logo') || srcLower.includes('icon') ||
                    srcLower.includes('avatar') || srcLower.includes('placeholder')) return;

                images.push({
                    src: src,
                    alt: img.alt || '',
                    width: width,
                    height: height
                });
            });
            return images;
        }''')

        for idx, img in enumerate(img_data or []):
            src = img['src']
            if src in seen:
                continue
            seen.add(src)

            # Try to get highest resolution
            src = self._get_high_res_url(src)

            images.append({
                "source": self.name,
                "source_id": f"{self.name}_{hash(src) % 10**8}",
                "source_url": source_url,
                "image_url": src,
                "thumbnail_url": src,
                "title": f"{self.brand_name} Interior",
                "description": img.get('alt', ''),
                "prompt": None,
                "width": img.get('width', 0),
                "height": img.get('height', 0),
                "engagement": 0,
                "style_tags": ["scandinavian", "real_photo"],
            })

        return images

    def _get_high_res_url(self, url: str) -> str:
        """Try to get higher resolution version of image URL."""
        # Common CDN patterns for higher res
        url = re.sub(r'w_\d+', 'w_1600', url)
        url = re.sub(r'h_\d+', 'h_1200', url)
        url = re.sub(r'/\d+x\d+/', '/1600x1200/', url)
        url = re.sub(r'_small|_thumb|_medium', '_large', url)
        return url


class BoliaSource(BrandScraperBase):
    """Bolia.com - Danish furniture with beautiful room settings."""

    name = "bolia"
    brand_name = "Bolia"
    base_url = "https://www.bolia.com"
    inspiration_urls = [
        "https://www.bolia.com/en/furniture/living-room/",
        "https://www.bolia.com/en/furniture/bedroom/",
        "https://www.bolia.com/en/furniture/dining-room/",
        "https://www.bolia.com/en/furniture/home-office/",
    ]


class HAYSource(BrandScraperBase):
    """HAY - Danish design brand."""

    name = "hay"
    brand_name = "HAY"
    base_url = "https://www.hay.com"
    inspiration_urls = [
        "https://www.hay.com/en-us/furniture",
        "https://www.hay.com/en-us/lighting",
        "https://www.hay.com/en-us/accessories",
    ]


class MuutoSource(BrandScraperBase):
    """Muuto - Scandinavian design."""

    name = "muuto"
    brand_name = "Muuto"
    base_url = "https://www.muuto.com"
    inspiration_urls = [
        "https://www.muuto.com/products",
        "https://www.muuto.com/products/seating",
        "https://www.muuto.com/products/tables",
        "https://www.muuto.com/products/storage",
    ]


class NormannSource(BrandScraperBase):
    """Normann Copenhagen."""

    name = "normann"
    brand_name = "Normann Copenhagen"
    base_url = "https://www.normann-copenhagen.com"
    inspiration_urls = [
        "https://www.normann-copenhagen.com/en/inspiration",
        "https://www.normann-copenhagen.com/en/categories/furniture",
    ]


class FermLivingSource(BrandScraperBase):
    """Ferm Living - Danish design."""

    name = "fermliving"
    brand_name = "Ferm Living"
    base_url = "https://www.fermliving.com"
    inspiration_urls = [
        "https://fermliving.com/pages/the-living-room",
        "https://fermliving.com/pages/the-dining-room",
        "https://fermliving.com/pages/the-bedroom",
        "https://fermliving.com/pages/the-kids-room",
    ]


class StringSource(BrandScraperBase):
    """String Furniture - Swedish shelving systems."""

    name = "string"
    brand_name = "String Furniture"
    base_url = "https://www.stringfurniture.com"
    inspiration_urls = [
        "https://www.stringfurniture.com/en-gb/inspiration/living-room",
        "https://www.stringfurniture.com/en-gb/inspiration/workspace",
        "https://www.stringfurniture.com/en-gb/inspiration/hallway",
        "https://www.stringfurniture.com/en-gb/inspiration/kitchen",
        "https://www.stringfurniture.com/en-gb/inspiration/bathroom",
    ]


class MenuSource(BrandScraperBase):
    """Menu / Audo Copenhagen."""

    name = "menu"
    brand_name = "Audo Copenhagen"
    base_url = "https://www.audo.com"
    inspiration_urls = [
        "https://audo.com/inspiration",
        "https://audo.com/collections/lounge",
        "https://audo.com/collections/dining",
    ]


class BoConceptSource(BrandScraperBase):
    """BoConcept - Danish furniture."""

    name = "boconcept"
    brand_name = "BoConcept"
    base_url = "https://www.boconcept.com"
    inspiration_urls = [
        "https://www.boconcept.com/en-us/inspiration/",
        "https://www.boconcept.com/en-us/inspiration/living/",
        "https://www.boconcept.com/en-us/inspiration/dining/",
        "https://www.boconcept.com/en-us/inspiration/bedroom/",
    ]


class IKEASource(BrandScraperBase):
    """IKEA - Room inspiration galleries."""

    name = "ikea"
    brand_name = "IKEA"
    base_url = "https://www.ikea.com"
    inspiration_urls = [
        "https://www.ikea.com/us/en/rooms/living-room/",
        "https://www.ikea.com/us/en/rooms/bedroom/",
        "https://www.ikea.com/us/en/rooms/kitchen/",
        "https://www.ikea.com/us/en/rooms/home-office/",
        "https://www.ikea.com/us/en/rooms/dining/",
        "https://www.ikea.com/us/en/rooms/bathroom/",
        "https://www.ikea.com/us/en/rooms/childrens-room/",
    ]

    def _extract_images(self, page, source_url: str) -> List[Dict]:
        """IKEA-specific extraction - they use specific image patterns."""
        images = []
        seen = set()

        img_data = page.evaluate('''() => {
            const images = [];

            // IKEA uses picture elements with srcset
            document.querySelectorAll('picture source, img').forEach(el => {
                let src = null;

                if (el.tagName === 'SOURCE') {
                    const srcset = el.getAttribute('srcset');
                    if (srcset) {
                        // Get the largest image from srcset
                        const sources = srcset.split(',').map(s => s.trim());
                        const largest = sources[sources.length - 1];
                        src = largest.split(' ')[0];
                    }
                } else {
                    src = el.src || el.dataset.src;
                }

                if (!src) return;

                // IKEA image patterns
                if (!src.includes('ikea.com') && !src.includes('ikeaimg')) return;

                // Skip tiny images
                if (src.includes('_s1') || src.includes('_s2') || src.includes('_s3')) return;

                // Prefer high-res versions
                src = src.replace(/_s\d+/, '_s5');

                if (!images.find(i => i.src === src)) {
                    images.push({
                        src: src,
                        alt: el.alt || '',
                        width: 1200,
                        height: 800
                    });
                }
            });

            return images;
        }''')

        for img in img_data or []:
            src = img['src']
            if src in seen:
                continue
            seen.add(src)

            # Detect room type from URL
            room_type = 'other'
            url_lower = source_url.lower()
            if 'living' in url_lower:
                room_type = 'living_room'
            elif 'bedroom' in url_lower:
                room_type = 'bedroom'
            elif 'kitchen' in url_lower:
                room_type = 'kitchen'
            elif 'office' in url_lower:
                room_type = 'office'
            elif 'dining' in url_lower:
                room_type = 'dining'
            elif 'bathroom' in url_lower:
                room_type = 'bathroom'
            elif 'hallway' in url_lower:
                room_type = 'hallway'

            images.append({
                "source": self.name,
                "source_id": f"ikea_{hash(src) % 10**8}",
                "source_url": source_url,
                "image_url": src,
                "thumbnail_url": src,
                "title": f"IKEA {room_type.replace('_', ' ').title()}",
                "description": img.get('alt', ''),
                "prompt": None,
                "width": img.get('width', 0),
                "height": img.get('height', 0),
                "engagement": 0,
                "room_type": room_type,
                "style_tags": ["scandinavian", "real_photo", "ikea"],
            })

        return images


# Convenience class that scrapes all brands
class AllBrandsSource(BaseSource):
    """Scrape from all Scandinavian furniture brands."""

    name = "brands"

    BRAND_SOURCES = [
        BoliaSource,
        HAYSource,
        MuutoSource,
        NormannSource,
        FermLivingSource,
        StringSource,
        MenuSource,
        BoConceptSource,
        IKEASource,
    ]

    def search(
        self,
        query: str = None,
        room_type: str = None,
        limit: int = 50
    ) -> Generator[Dict, None, None]:
        """Scrape from all brands, distributing limit across them."""
        per_brand = max(limit // len(self.BRAND_SOURCES), 10)
        found = 0

        for source_class in self.BRAND_SOURCES:
            if found >= limit:
                break

            source = source_class()
            brand_found = 0

            for result in source.search(query=query, room_type=room_type, limit=per_brand):
                if found >= limit:
                    break
                found += 1
                brand_found += 1
                yield result

            print(f"  {source.brand_name}: {brand_found} images")

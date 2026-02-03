"""
Design magazine and editorial scrapers.
High-quality interior photography from design publications.
"""

import re
from typing import Generator, Dict, List
from urllib.parse import urljoin

try:
    from playwright.sync_api import sync_playwright
    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False

from ..base import BaseSource


class MagazineScraperBase(BaseSource):
    """Base class for design magazine scrapers."""

    name = "magazine"
    magazine_name = "Generic"
    base_url = ""
    article_list_urls = []  # URLs containing lists of articles
    article_selector = "a"  # CSS selector for article links

    def search(
        self,
        query: str = None,
        room_type: str = None,
        limit: int = 50
    ) -> Generator[Dict, None, None]:
        """Scrape interior images from magazine articles."""
        if not HAS_PLAYWRIGHT:
            print("Playwright required.")
            return

        found = 0

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
            )
            page = context.new_page()

            try:
                for list_url in self.article_list_urls:
                    if found >= limit:
                        break

                    print(f"  {self.magazine_name}: {list_url}")

                    try:
                        page.goto(list_url, wait_until='networkidle', timeout=30000)
                        page.wait_for_timeout(2000)

                        # Scroll to load more articles
                        for _ in range(3):
                            page.evaluate('window.scrollBy(0, window.innerHeight)')
                            page.wait_for_timeout(500)

                        images = self._extract_images(page, list_url)

                        for img in images:
                            if found >= limit:
                                break
                            found += 1
                            yield img

                    except Exception as e:
                        print(f"    Error: {e}")

            finally:
                browser.close()

    def _extract_images(self, page, source_url: str) -> List[Dict]:
        """Extract high-quality images from page."""
        images = []
        seen = set()

        img_data = page.evaluate('''() => {
            const images = [];
            document.querySelectorAll('img').forEach(img => {
                let src = img.src || img.dataset.src || img.dataset.lazySrc ||
                          img.getAttribute('data-srcset')?.split(',')[0]?.split(' ')[0];
                if (!src) return;

                // Get natural dimensions
                const width = img.naturalWidth || parseInt(img.getAttribute('width')) || 0;
                const height = img.naturalHeight || parseInt(img.getAttribute('height')) || 0;

                // Skip small images
                if (width < 600 || height < 400) return;

                // Skip common non-content
                const srcLower = src.toLowerCase();
                if (srcLower.includes('logo') || srcLower.includes('icon') ||
                    srcLower.includes('avatar') || srcLower.includes('ad-') ||
                    srcLower.includes('banner') || srcLower.includes('sponsor')) return;

                images.push({
                    src: src,
                    alt: img.alt || '',
                    width: width,
                    height: height
                });
            });
            return images;
        }''')

        for img in img_data or []:
            src = img['src']
            if src in seen or not src.startswith('http'):
                continue
            seen.add(src)

            # Try to upgrade to high-res
            src = self._upgrade_resolution(src)

            images.append({
                "source": self.name,
                "source_id": f"{self.name}_{hash(src) % 10**8}",
                "source_url": source_url,
                "image_url": src,
                "thumbnail_url": img['src'],
                "title": f"{self.magazine_name}",
                "description": img.get('alt', ''),
                "prompt": None,
                "width": img.get('width', 0),
                "height": img.get('height', 0),
                "engagement": 0,
                "style_tags": ["editorial", "real_photo"],
            })

        return images

    def _upgrade_resolution(self, url: str) -> str:
        """Try to get higher resolution version."""
        # Common patterns
        url = re.sub(r'-\d{3,4}x\d{3,4}\.', '.', url)  # Remove WP thumbnails
        url = re.sub(r'\?w=\d+', '?w=1600', url)
        url = re.sub(r'\?width=\d+', '?width=1600', url)
        url = re.sub(r'&w=\d+', '&w=1600', url)
        url = re.sub(r'/resize/\d+x\d+/', '/resize/1600x0/', url)
        return url


class DezeenSource(MagazineScraperBase):
    """Dezeen - Architecture and interior design magazine."""

    name = "dezeen"
    magazine_name = "Dezeen"
    base_url = "https://www.dezeen.com"
    article_list_urls = [
        "https://www.dezeen.com/interiors/",
        "https://www.dezeen.com/interiors/residential-interiors/",
        "https://www.dezeen.com/interiors/living-spaces/",
        "https://www.dezeen.com/interiors/kitchens/",
        "https://www.dezeen.com/interiors/bedrooms/",
        "https://www.dezeen.com/interiors/bathrooms/",
        "https://www.dezeen.com/tag/scandinavian-interiors/",
    ]


class ArchDailySource(MagazineScraperBase):
    """ArchDaily - Architecture and interiors."""

    name = "archdaily"
    magazine_name = "ArchDaily"
    base_url = "https://www.archdaily.com"
    article_list_urls = [
        "https://www.archdaily.com/search/projects/categories/interior-design",
        "https://www.archdaily.com/search/projects/categories/houses",
        "https://www.archdaily.com/search/projects/categories/apartments",
    ]


class YellowtraceSource(MagazineScraperBase):
    """Yellowtrace - Australian design blog with great interiors."""

    name = "yellowtrace"
    magazine_name = "Yellowtrace"
    base_url = "https://www.yellowtrace.com.au"
    article_list_urls = [
        "https://www.yellowtrace.com.au/category/architecture-design/residential/",
        "https://www.yellowtrace.com.au/category/architecture-design/commercial/",
    ]


class TheNordicroomSource(MagazineScraperBase):
    """The Nordroom - Scandinavian interior design blog."""

    name = "nordroom"
    magazine_name = "The Nordroom"
    base_url = "https://www.thenordroom.com"
    article_list_urls = [
        "https://www.thenordroom.com/",
        "https://www.thenordroom.com/category/living-room/",
        "https://www.thenordroom.com/category/bedroom/",
        "https://www.thenordroom.com/category/kitchen/",
        "https://www.thenordroom.com/category/bathroom/",
    ]


class MyScandinavianHomeSource(MagazineScraperBase):
    """My Scandinavian Home - Curated Nordic interiors."""

    name = "myscandinavianhome"
    magazine_name = "My Scandinavian Home"
    base_url = "https://www.myscandinavianhome.com"
    article_list_urls = [
        "https://www.myscandinavianhome.com/",
        "https://www.myscandinavianhome.com/search/label/Home%20Tours",
        "https://www.myscandinavianhome.com/search/label/Living%20Rooms",
        "https://www.myscandinavianhome.com/search/label/Kitchens",
    ]


class CocoCottonSource(MagazineScraperBase):
    """COCO LAPINE DESIGN - Scandinavian interiors."""

    name = "cocolapine"
    magazine_name = "Coco Lapine Design"
    base_url = "https://cocolapinedesign.com"
    article_list_urls = [
        "https://cocolapinedesign.com/category/interior/",
        "https://cocolapinedesign.com/category/home-tour/",
    ]


class ResidenceMagSource(MagazineScraperBase):
    """Residence Magazine - Swedish interior design magazine."""

    name = "residence"
    magazine_name = "Residence Magazine"
    base_url = "https://residencemagazine.se"
    article_list_urls = [
        "https://residencemagazine.se/kategori/inredning/",
        "https://residencemagazine.se/kategori/hemma-hos/",
    ]


class BoBedreSource(MagazineScraperBase):
    """Bo Bedre - Norwegian interior magazine."""

    name = "bobedre"
    magazine_name = "Bo Bedre"
    base_url = "https://www.bobedre.no"
    article_list_urls = [
        "https://www.bobedre.no/interiortips",
        "https://www.bobedre.no/interior/stue",
        "https://www.bobedre.no/interior/kjokken",
        "https://www.bobedre.no/interior/soverom",
        "https://www.bobedre.no/interior/bad",
    ]


# Convenience class for all magazines
class AllMagazinesSource(BaseSource):
    """Scrape from all design magazines."""

    name = "magazines"

    MAGAZINE_SOURCES = [
        DezeenSource,
        ArchDailySource,
        YellowtraceSource,
        TheNordicroomSource,
        MyScandinavianHomeSource,
        CocoCottonSource,
        ResidenceMagSource,
        BoBedreSource,
    ]

    def search(
        self,
        query: str = None,
        room_type: str = None,
        limit: int = 50
    ) -> Generator[Dict, None, None]:
        """Scrape from all magazines."""
        per_mag = max(limit // len(self.MAGAZINE_SOURCES), 10)
        found = 0

        for source_class in self.MAGAZINE_SOURCES:
            if found >= limit:
                break

            source = source_class()
            mag_found = 0

            for result in source.search(query=query, room_type=room_type, limit=per_mag):
                if found >= limit:
                    break
                found += 1
                mag_found += 1
                yield result

            print(f"  {source.magazine_name}: {mag_found} images")

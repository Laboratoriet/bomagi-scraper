"""
Simple brand scrapers using requests + BeautifulSoup
No Playwright required - uses RSS feeds, sitemaps, and static HTML
"""

import requests
from bs4 import BeautifulSoup
import re
from typing import Generator, Dict, Any, Optional
from urllib.parse import urljoin

from ..base import BaseSource, classify_room_type

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
}


class SimpleBrandScraper(BaseSource):
    """Base class for simple request-based scrapers"""

    name = "simple_brand"
    base_url = ""

    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)
        self.session = requests.Session()
        self.session.headers.update(HEADERS)

    def get_page(self, url: str) -> Optional[BeautifulSoup]:
        """Fetch and parse a page"""
        try:
            resp = self.session.get(url, timeout=30)
            resp.raise_for_status()
            return BeautifulSoup(resp.text, 'html.parser')
        except Exception as e:
            print(f"  Error fetching {url}: {e}")
            return None

    def extract_high_res_url(self, img_url: str) -> str:
        """Try to get highest resolution version of image"""
        patterns = [
            (r'_\d+x\d+\.', '.'),
            (r'-\d+x\d+\.', '.'),
            (r'\?w=\d+.*$', ''),
            (r'&w=\d+', ''),
            (r'/w_\d+,', '/'),
        ]
        for pattern, replacement in patterns:
            img_url = re.sub(pattern, replacement, img_url)
        return img_url

    def search(self, query: str, room_type: str = None, limit: int = 50) -> Generator[Dict, None, None]:
        """Override in subclass"""
        pass


class DesignMilkSource(SimpleBrandScraper):
    """Design Milk - design blog with great interior content"""

    name = "designmilk"
    base_url = "https://design-milk.com"

    def search(self, query: str, room_type: str = None, limit: int = 50) -> Generator[Dict, None, None]:
        count = 0
        categories = [
            '/category/interior-design/',
            '/category/interior-design/living-spaces/',
            '/category/interior-design/kitchens/',
            '/category/interior-design/bedrooms-2/',
            '/category/interior-design/bathrooms/',
        ]

        for cat_url in categories:
            if count >= limit:
                break

            soup = self.get_page(f"{self.base_url}{cat_url}")
            if not soup:
                continue

            for article in soup.select('article.post'):
                if count >= limit:
                    break

                img = article.select_one('img.wp-post-image, img.attachment-large')
                if not img:
                    continue

                img_url = img.get('src') or img.get('data-src')
                if not img_url:
                    continue

                img_url = self.extract_high_res_url(img_url)

                title_el = article.select_one('h2.entry-title a, .entry-title a')
                title = title_el.text.strip() if title_el else ""
                link = title_el.get('href') if title_el else ""

                detected_room = classify_room_type(title + " " + (img.get('alt') or ''))
                if room_type and detected_room != room_type:
                    continue

                count += 1
                yield {
                    'source': self.name,
                    'source_id': img_url.split('/')[-1].split('.')[0][:50],
                    'image_url': img_url,
                    'thumbnail_url': img_url,
                    'title': title[:200],
                    'source_url': link,
                    'room_type': detected_room,
                }


class YellowtraceLightSource(SimpleBrandScraper):
    """Yellowtrace - simpler version without Playwright"""

    name = "yellowtrace"
    base_url = "https://www.yellowtrace.com.au"

    def search(self, query: str, room_type: str = None, limit: int = 50) -> Generator[Dict, None, None]:
        count = 0
        categories = [
            '/category/architecture-and-interiors/residential/',
            '/category/architecture-and-interiors/hospitality/',
            '/category/architecture-and-interiors/retail/',
        ]

        for cat_url in categories:
            if count >= limit:
                break

            soup = self.get_page(f"{self.base_url}{cat_url}")
            if not soup:
                continue

            for article in soup.select('article, .post-item'):
                if count >= limit:
                    break

                img = article.select_one('img')
                if not img:
                    continue

                img_url = img.get('src') or img.get('data-src') or img.get('data-lazy-src')
                if not img_url or 'placeholder' in img_url.lower():
                    continue

                img_url = self.extract_high_res_url(img_url)
                if not img_url.startswith('http'):
                    img_url = urljoin(self.base_url, img_url)

                title_el = article.select_one('h2 a, h3 a, .entry-title a')
                title = title_el.text.strip() if title_el else img.get('alt', '')
                link = title_el.get('href') if title_el else ''

                detected_room = classify_room_type(title)

                count += 1
                yield {
                    'source': self.name,
                    'source_id': str(hash(img_url))[:12],
                    'image_url': img_url,
                    'thumbnail_url': img_url,
                    'title': title[:200],
                    'source_url': link,
                    'room_type': detected_room,
                }


class DezeenSimpleSource(SimpleBrandScraper):
    """Dezeen - architecture and design magazine"""

    name = "dezeen"
    base_url = "https://www.dezeen.com"

    def search(self, query: str, room_type: str = None, limit: int = 50) -> Generator[Dict, None, None]:
        count = 0
        urls = [
            '/interiors/',
            '/interiors/residential-interiors/',
            '/interiors/kitchen-interiors/',
            '/interiors/bathroom-interiors/',
            '/interiors/living-room-interiors/',
            '/interiors/bedroom-interiors/',
        ]

        for url_path in urls:
            if count >= limit:
                break

            soup = self.get_page(f"{self.base_url}{url_path}")
            if not soup:
                continue

            for article in soup.select('article, .dezeen-post, li[class*="post"]'):
                if count >= limit:
                    break

                img = article.select_one('img')
                if not img:
                    continue

                srcset = img.get('srcset', '')
                img_url = None

                if srcset:
                    parts = srcset.split(',')
                    best_width = 0
                    for part in parts:
                        match = re.search(r'(https?://[^\s]+)\s+(\d+)w', part.strip())
                        if match:
                            url, width = match.groups()
                            if int(width) > best_width:
                                best_width = int(width)
                                img_url = url

                if not img_url:
                    img_url = img.get('src') or img.get('data-src')

                if not img_url or 'placeholder' in img_url.lower():
                    continue

                title_el = article.select_one('h3 a, h2 a, .dezeen-post-title a')
                title = title_el.text.strip() if title_el else img.get('alt', '')
                link = title_el.get('href') if title_el else ''

                if link and not link.startswith('http'):
                    link = urljoin(self.base_url, link)

                detected_room = classify_room_type(title + " " + url_path)
                if room_type and detected_room != room_type:
                    continue

                count += 1
                yield {
                    'source': self.name,
                    'source_id': str(hash(img_url))[:12],
                    'image_url': img_url,
                    'thumbnail_url': img_url,
                    'title': title[:200],
                    'source_url': link,
                    'room_type': detected_room,
                }


class ArchDailySimpleSource(SimpleBrandScraper):
    """ArchDaily - architecture news with interior content"""

    name = "archdaily"
    base_url = "https://www.archdaily.com"

    def search(self, query: str, room_type: str = None, limit: int = 50) -> Generator[Dict, None, None]:
        count = 0
        search_url = f"{self.base_url}/search/projects/categories/houses?q={query}"
        soup = self.get_page(search_url)

        if not soup:
            soup = self.get_page(f"{self.base_url}/search/projects?q=scandinavian+interior")

        if not soup:
            return

        for article in soup.select('article, .afd-search-list__item, li[data-url]'):
            if count >= limit:
                break

            img = article.select_one('img')
            if not img:
                continue

            img_url = img.get('data-src') or img.get('src') or img.get('data-lazy-src')
            if not img_url:
                continue

            if 'thumbor' in img_url or 'images.adsttc' in img_url:
                img_url = re.sub(r'/\d+x\d+_', '/', img_url)

            if not img_url.startswith('http'):
                img_url = urljoin(self.base_url, img_url)

            title_el = article.select_one('h2, h3, .afd-title')
            title = title_el.text.strip() if title_el else img.get('alt', '')

            link = article.get('data-url') or ''
            if not link:
                link_el = article.select_one('a[href*="/"]')
                link = link_el.get('href', '') if link_el else ''

            if link and not link.startswith('http'):
                link = urljoin(self.base_url, link)

            detected_room = classify_room_type(title)

            count += 1
            yield {
                'source': self.name,
                'source_id': str(hash(img_url))[:12],
                'image_url': img_url,
                'thumbnail_url': img_url,
                'title': title[:200],
                'source_url': link,
                'room_type': detected_room,
            }


class NordroomSource(SimpleBrandScraper):
    """The Nordroom - Scandinavian interior blog"""

    name = "nordroom"
    base_url = "https://www.thenordroom.com"

    def search(self, query: str, room_type: str = None, limit: int = 50) -> Generator[Dict, None, None]:
        count = 0
        categories = [
            '/category/living-room/',
            '/category/bedroom/',
            '/category/kitchen/',
            '/category/bathroom/',
            '/category/scandinavian-interior/',
            '/category/home-tour/',
        ]

        for cat_url in categories:
            if count >= limit:
                break

            soup = self.get_page(f"{self.base_url}{cat_url}")
            if not soup:
                continue

            for article in soup.select('article, .post'):
                if count >= limit:
                    break

                for img in article.select('img'):
                    if count >= limit:
                        break

                    img_url = img.get('src') or img.get('data-src')
                    if not img_url or 'avatar' in img_url.lower() or 'logo' in img_url.lower():
                        continue

                    width = img.get('width', '0')
                    try:
                        if width and int(width) < 300:
                            continue
                    except:
                        pass

                    img_url = self.extract_high_res_url(img_url)
                    if not img_url.startswith('http'):
                        img_url = urljoin(self.base_url, img_url)

                    title_el = article.select_one('h2 a, .entry-title a')
                    title = title_el.text.strip() if title_el else img.get('alt', '')
                    link = title_el.get('href') if title_el else ''

                    detected_room = 'other'
                    if 'living' in cat_url:
                        detected_room = 'living_room'
                    elif 'bedroom' in cat_url:
                        detected_room = 'bedroom'
                    elif 'kitchen' in cat_url:
                        detected_room = 'kitchen'
                    elif 'bathroom' in cat_url:
                        detected_room = 'bathroom'
                    else:
                        detected_room = classify_room_type(title) or 'other'

                    if room_type and detected_room != room_type:
                        continue

                    count += 1
                    yield {
                        'source': self.name,
                        'source_id': str(hash(img_url))[:12],
                        'image_url': img_url,
                        'thumbnail_url': img_url,
                        'title': title[:200],
                        'source_url': link,
                        'room_type': detected_room,
                    }


class CocoLapineSource(SimpleBrandScraper):
    """Coco Lapine Design - Scandinavian interior blog"""

    name = "cocolapine"
    base_url = "https://cocolapinedesign.com"

    def search(self, query: str, room_type: str = None, limit: int = 50) -> Generator[Dict, None, None]:
        count = 0
        pages = [
            '/category/interior/',
            '/category/interiors/',
            '/category/home-tour/',
            '/',
        ]

        for page_url in pages:
            if count >= limit:
                break

            soup = self.get_page(f"{self.base_url}{page_url}")
            if not soup:
                continue

            for article in soup.select('article, .post, .entry'):
                if count >= limit:
                    break

                img = article.select_one('img.wp-post-image, img.attachment-large, img[src*="upload"]')
                if not img:
                    img = article.select_one('img')

                if not img:
                    continue

                img_url = img.get('src') or img.get('data-src')
                if not img_url or 'gravatar' in img_url or 'avatar' in img_url:
                    continue

                img_url = self.extract_high_res_url(img_url)
                if not img_url.startswith('http'):
                    img_url = urljoin(self.base_url, img_url)

                title_el = article.select_one('h2 a, h3 a, .entry-title a')
                title = title_el.text.strip() if title_el else img.get('alt', '')
                link = title_el.get('href') if title_el else ''

                detected_room = classify_room_type(title) or 'other'

                count += 1
                yield {
                    'source': self.name,
                    'source_id': str(hash(img_url))[:12],
                    'image_url': img_url,
                    'thumbnail_url': img_url,
                    'title': title[:200],
                    'source_url': link,
                    'room_type': detected_room,
                }


class MyScandinavianHomeSource(SimpleBrandScraper):
    """My Scandinavian Home blog"""

    name = "myscandinavianhome"
    base_url = "https://www.myscandinavianhome.com"

    def search(self, query: str, room_type: str = None, limit: int = 50) -> Generator[Dict, None, None]:
        count = 0
        soup = self.get_page(f"{self.base_url}/search?q={query}")
        if not soup:
            soup = self.get_page(self.base_url)

        if not soup:
            return

        for article in soup.select('article, .post-outer, .blog-post'):
            if count >= limit:
                break

            for img in article.select('img'):
                if count >= limit:
                    break

                img_url = img.get('src') or img.get('data-src')
                if not img_url:
                    continue

                if 'icon' in img_url.lower() or 'logo' in img_url.lower():
                    continue

                if 'blogspot' in img_url:
                    img_url = re.sub(r'/s\d+/', '/s1600/', img_url)
                    img_url = re.sub(r'/w\d+-h\d+/', '/s1600/', img_url)

                if not img_url.startswith('http'):
                    img_url = urljoin(self.base_url, img_url)

                title_el = article.select_one('h2 a, h3 a, .post-title a')
                title = title_el.text.strip() if title_el else img.get('alt', '')
                link = title_el.get('href') if title_el else ''

                detected_room = classify_room_type(title) or 'other'

                count += 1
                yield {
                    'source': self.name,
                    'source_id': str(hash(img_url))[:12],
                    'image_url': img_url,
                    'thumbnail_url': img_url,
                    'title': title[:200],
                    'source_url': link,
                    'room_type': detected_room,
                }


class AllSimpleSourcesCombined(BaseSource):
    """Scrape all simple sources that don't require Playwright"""

    name = "all_simple"

    def search(self, query: str, room_type: str = None, limit: int = 50) -> Generator[Dict, None, None]:
        sources = [
            DezeenSimpleSource(),
            NordroomSource(),
            CocoLapineSource(),
            MyScandinavianHomeSource(),
            YellowtraceLightSource(),
            ArchDailySimpleSource(),
            DesignMilkSource(),
        ]

        total = 0
        per_source_limit = max(10, limit // len(sources))

        for source in sources:
            if total >= limit:
                break

            print(f"  Scraping {source.name}...")
            source_count = 0
            try:
                for result in source.search(query, room_type, per_source_limit):
                    if total >= limit:
                        break
                    source_count += 1
                    total += 1
                    yield result
                print(f"    Found {source_count} images")
            except Exception as e:
                print(f"    Error: {e}")


# Export all sources
SIMPLE_SOURCES = {
    'all_simple': AllSimpleSourcesCombined,
    'dezeen': DezeenSimpleSource,
    'archdaily': ArchDailySimpleSource,
    'nordroom': NordroomSource,
    'cocolapine': CocoLapineSource,
    'myscandinavianhome': MyScandinavianHomeSource,
    'yellowtrace': YellowtraceLightSource,
    'designmilk': DesignMilkSource,
}

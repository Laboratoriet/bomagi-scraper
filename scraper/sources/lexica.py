"""Lexica.art source adapter - Stable Diffusion image search."""
import requests
from typing import Generator, Dict, Any
from ..base import BaseSource


class LexicaSource(BaseSource):
    """
    Lexica.art image source.
    Unofficial API - reverse engineered from their web interface.
    """

    name = "lexica"
    requires_auth = False

    BASE_URL = "https://lexica.art/api/v1"

    def search(
        self,
        query: str = "interior design scandinavian",
        room_type: str = None,
        limit: int = 50
    ) -> Generator[Dict, None, None]:
        """
        Search Lexica for images.
        Uses their search endpoint.
        """
        # Build search query
        search_query = query
        if room_type:
            room_name = room_type.replace('_', ' ')
            search_query = f"{room_name} interior {query}"

        found = 0

        try:
            # Lexica's search endpoint
            response = requests.get(
                f"{self.BASE_URL}/search",
                params={"q": search_query},
                timeout=30
            )
            response.raise_for_status()
            data = response.json()
        except Exception as e:
            print(f"Lexica API error: {e}")
            return

        images = data.get("images", [])

        for item in images:
            if found >= limit:
                break

            result = self._parse_image(item)
            if result:
                found += 1
                yield result

    def _parse_image(self, item: Dict) -> Dict[str, Any]:
        """Parse a Lexica image item into our format."""
        try:
            image_id = item.get("id", "")
            if not image_id:
                return None

            # Lexica image URLs
            # Full: https://lexica-serve-encoded-images2.sharif.workers.dev/full_jpg/{id}
            # Thumbnail: https://lexica-serve-encoded-images2.sharif.workers.dev/sm2/{id}
            image_url = f"https://lexica-serve-encoded-images2.sharif.workers.dev/full_jpg/{image_id}"
            thumbnail_url = f"https://lexica-serve-encoded-images2.sharif.workers.dev/sm2/{image_id}"

            # Get prompt
            prompt = item.get("prompt", "")

            # Dimensions
            width = item.get("width", 0)
            height = item.get("height", 0)

            # Lexica doesn't provide engagement metrics publicly
            # But we can infer quality from being in search results

            # Extract style tags from prompt
            tags = []
            if prompt:
                style_words = [
                    "minimalist", "scandinavian", "modern", "cozy", "rustic",
                    "industrial", "bohemian", "contemporary", "traditional",
                    "mid-century", "art deco", "japanese", "nordic", "hygge",
                    "warm", "bright", "natural light", "wooden"
                ]
                prompt_lower = prompt.lower()
                tags = [w for w in style_words if w in prompt_lower]

            # Source URL (Lexica prompt page)
            source_url = f"https://lexica.art/prompt/{image_id}"

            return {
                "source": self.name,
                "source_id": image_id,
                "source_url": source_url,
                "image_url": image_url,
                "thumbnail_url": thumbnail_url,
                "title": None,
                "description": None,
                "prompt": prompt[:2000] if prompt else None,
                "width": width,
                "height": height,
                "engagement": 0,  # Lexica doesn't expose this
                "style_tags": tags if tags else None,
            }

        except Exception as e:
            print(f"Error parsing Lexica item: {e}")
            return None

    def get_similar(self, image_id: str, limit: int = 20) -> Generator[Dict, None, None]:
        """Get images similar to a given image ID."""
        try:
            response = requests.get(
                f"{self.BASE_URL}/search",
                params={"q": f"similar:{image_id}"},
                timeout=30
            )
            response.raise_for_status()
            data = response.json()
        except Exception as e:
            print(f"Lexica similar search error: {e}")
            return

        found = 0
        for item in data.get("images", []):
            if found >= limit:
                break
            result = self._parse_image(item)
            if result:
                found += 1
                yield result

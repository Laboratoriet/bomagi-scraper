"""Civitai source adapter - Official API."""
import requests
from typing import Generator, Dict, Any
from ..base import BaseSource


class CivitaiSource(BaseSource):
    """
    Civitai image source using their official REST API.
    Docs: https://github.com/civitai/civitai/wiki/REST-API-Reference
    """

    name = "civitai"
    requires_auth = False

    BASE_URL = "https://civitai.com/api/v1"

    # Interior design related tags and models
    INTERIOR_TAGS = [
        "interior design", "interior", "architecture", "room",
        "living room", "kitchen", "bedroom", "bathroom",
        "scandinavian", "minimalist", "modern", "cozy"
    ]

    def search(
        self,
        query: str = "interior design",
        room_type: str = None,
        limit: int = 50
    ) -> Generator[Dict, None, None]:
        """
        Search Civitai for interior images.
        Uses the /images endpoint.
        """
        # Build search query
        search_query = query
        if room_type:
            search_query = f"{room_type.replace('_', ' ')} {query}"

        params = {
            "limit": min(limit, 100),  # API max is 100 per page
            "sort": "Most Reactions",
            "period": "AllTime",
            "nsfw": "false",
        }

        # Add query as tag search
        if search_query:
            params["query"] = search_query

        found = 0
        cursor = None

        while found < limit:
            if cursor:
                params["cursor"] = cursor

            try:
                response = requests.get(
                    f"{self.BASE_URL}/images",
                    params=params,
                    timeout=30
                )
                response.raise_for_status()
                data = response.json()
            except Exception as e:
                print(f"Civitai API error: {e}")
                break

            items = data.get("items", [])
            if not items:
                break

            for item in items:
                if found >= limit:
                    break

                # Extract image data
                result = self._parse_image(item)
                if result:
                    found += 1
                    yield result

            # Get next page cursor
            metadata = data.get("metadata", {})
            cursor = metadata.get("nextCursor")
            if not cursor:
                break

    def _parse_image(self, item: Dict) -> Dict[str, Any]:
        """Parse a Civitai image item into our format."""
        try:
            image_id = str(item.get("id", ""))
            if not image_id:
                return None

            # Get the image URL
            url = item.get("url", "")
            if not url:
                return None

            # Get metadata
            meta = item.get("meta", {}) or {}

            # Extract prompt
            prompt = meta.get("prompt", "")

            # Get dimensions
            width = item.get("width", 0)
            height = item.get("height", 0)

            # Get engagement (reactions)
            stats = item.get("stats", {}) or {}
            engagement = sum([
                stats.get("heartCount", 0),
                stats.get("likeCount", 0),
                stats.get("laughCount", 0),
                stats.get("cryCount", 0),
            ])

            # Get tags from prompt
            tags = []
            if prompt:
                # Extract common style descriptors from prompt
                style_words = [
                    "minimalist", "scandinavian", "modern", "cozy", "rustic",
                    "industrial", "bohemian", "contemporary", "traditional",
                    "mid-century", "art deco", "japanese", "nordic"
                ]
                prompt_lower = prompt.lower()
                tags = [w for w in style_words if w in prompt_lower]

            return {
                "source": self.name,
                "source_id": image_id,
                "source_url": f"https://civitai.com/images/{image_id}",
                "image_url": url,
                "thumbnail_url": url,  # Civitai serves responsive images
                "title": None,
                "description": None,
                "prompt": prompt[:2000] if prompt else None,  # Truncate long prompts
                "width": width,
                "height": height,
                "engagement": engagement,
                "style_tags": tags if tags else None,
            }

        except Exception as e:
            print(f"Error parsing Civitai item: {e}")
            return None


def search_interior_models():
    """
    Helper to find interior design focused models on Civitai.
    Returns model IDs that can be used for more targeted searches.
    """
    url = "https://civitai.com/api/v1/models"
    params = {
        "query": "interior design",
        "sort": "Most Downloaded",
        "limit": 20,
    }

    try:
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()

        models = []
        for item in data.get("items", []):
            models.append({
                "id": item.get("id"),
                "name": item.get("name"),
                "type": item.get("type"),
                "downloads": item.get("stats", {}).get("downloadCount", 0),
            })
        return models

    except Exception as e:
        print(f"Error fetching models: {e}")
        return []

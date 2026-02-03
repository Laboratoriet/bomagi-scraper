"""
CLIP-based room type classification for interior images.

Uses OpenAI's CLIP model to classify images into room types
based on visual content rather than text/keywords.
"""

import os
from typing import Optional, List, Dict, Tuple
from pathlib import Path
from functools import lru_cache

try:
    import torch
    from PIL import Image
    from transformers import CLIPProcessor, CLIPModel
    HAS_CLIP = True
except ImportError:
    HAS_CLIP = False

try:
    import requests
    from io import BytesIO
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False


# Room type labels with descriptive prompts for CLIP
ROOM_LABELS = {
    'living_room': [
        "a photo of a living room",
        "a living room interior",
        "a cozy living room with sofa",
        "a modern living room",
    ],
    'kitchen': [
        "a photo of a kitchen",
        "a kitchen interior",
        "a modern kitchen with cabinets",
        "a kitchen with appliances",
    ],
    'bedroom': [
        "a photo of a bedroom",
        "a bedroom interior",
        "a cozy bedroom with bed",
        "a master bedroom",
    ],
    'bathroom': [
        "a photo of a bathroom",
        "a bathroom interior",
        "a modern bathroom with sink",
        "a bathroom with shower",
    ],
    'hallway': [
        "a photo of a hallway",
        "a hallway interior",
        "an entrance hallway",
        "a corridor in a home",
    ],
    'dining': [
        "a photo of a dining room",
        "a dining room interior",
        "a dining area with table",
        "a dining space",
    ],
    'office': [
        "a photo of a home office",
        "a home office interior",
        "a study room with desk",
        "a workspace at home",
    ],
    'outdoor': [
        "a photo of a balcony",
        "a terrace or patio",
        "an outdoor living space",
        "a garden or backyard",
    ],
}

# Style labels for additional classification
STYLE_LABELS = {
    'scandinavian': [
        "scandinavian interior design",
        "nordic minimalist interior",
        "swedish design style",
    ],
    'modern': [
        "modern interior design",
        "contemporary interior",
        "sleek modern decor",
    ],
    'minimalist': [
        "minimalist interior design",
        "minimal decor",
        "clean simple interior",
    ],
    'industrial': [
        "industrial interior design",
        "loft style interior",
        "exposed brick and metal",
    ],
    'bohemian': [
        "bohemian interior design",
        "boho decor style",
        "eclectic colorful interior",
    ],
    'traditional': [
        "traditional interior design",
        "classic home decor",
        "timeless elegant interior",
    ],
    'rustic': [
        "rustic interior design",
        "farmhouse style interior",
        "cozy cabin decor",
    ],
    'mid_century': [
        "mid-century modern interior",
        "retro 1960s style interior",
        "vintage modern design",
    ],
}


class CLIPClassifier:
    """
    CLIP-based image classifier for room types and styles.

    Usage:
        classifier = CLIPClassifier()
        room_type, confidence = classifier.classify_room(image_path_or_url)
        styles = classifier.classify_style(image_path_or_url)
    """

    def __init__(self, model_name: str = "openai/clip-vit-base-patch32", device: str = None):
        """
        Initialize the CLIP classifier.

        Args:
            model_name: HuggingFace model name (default: clip-vit-base-patch32)
            device: 'cuda', 'mps', or 'cpu' (auto-detected if None)
        """
        if not HAS_CLIP:
            raise ImportError(
                "CLIP dependencies not installed. Run:\n"
                "pip install torch transformers Pillow"
            )

        self.model_name = model_name
        self.device = device or self._detect_device()

        print(f"Loading CLIP model: {model_name} on {self.device}")
        self.model = CLIPModel.from_pretrained(model_name).to(self.device)
        self.processor = CLIPProcessor.from_pretrained(model_name)

        # Pre-compute text embeddings for labels
        self._room_embeddings = self._compute_label_embeddings(ROOM_LABELS)
        self._style_embeddings = self._compute_label_embeddings(STYLE_LABELS)

        print("CLIP classifier ready")

    def _detect_device(self) -> str:
        """Auto-detect best available device."""
        if torch.cuda.is_available():
            return "cuda"
        elif hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
            return "mps"
        return "cpu"

    def _compute_label_embeddings(self, labels: Dict[str, List[str]]) -> Dict[str, torch.Tensor]:
        """Pre-compute text embeddings for all labels."""
        embeddings = {}

        for label, prompts in labels.items():
            inputs = self.processor(text=prompts, return_tensors="pt", padding=True)
            inputs = {k: v.to(self.device) for k, v in inputs.items()}

            with torch.no_grad():
                text_features = self.model.get_text_features(**inputs)
                # Average embeddings for multiple prompts per label
                embeddings[label] = text_features.mean(dim=0)

        return embeddings

    def _load_image(self, image_source) -> Image.Image:
        """Load image from path, URL, or PIL Image."""
        if isinstance(image_source, Image.Image):
            return image_source.convert("RGB")

        if isinstance(image_source, (str, Path)):
            path = str(image_source)

            # URL
            if path.startswith(('http://', 'https://')):
                if not HAS_REQUESTS:
                    raise ImportError("requests library required for URL loading")
                response = requests.get(path, timeout=30)
                response.raise_for_status()
                return Image.open(BytesIO(response.content)).convert("RGB")

            # Local file
            return Image.open(path).convert("RGB")

        raise ValueError(f"Unsupported image source type: {type(image_source)}")

    def _get_image_embedding(self, image: Image.Image) -> torch.Tensor:
        """Get CLIP embedding for an image."""
        inputs = self.processor(images=image, return_tensors="pt")
        inputs = {k: v.to(self.device) for k, v in inputs.items()}

        with torch.no_grad():
            image_features = self.model.get_image_features(**inputs)

        return image_features[0]

    def _classify_with_embeddings(
        self,
        image_embedding: torch.Tensor,
        label_embeddings: Dict[str, torch.Tensor]
    ) -> List[Tuple[str, float]]:
        """Classify image using pre-computed label embeddings."""
        scores = {}

        for label, text_embedding in label_embeddings.items():
            # Cosine similarity
            similarity = torch.nn.functional.cosine_similarity(
                image_embedding.unsqueeze(0),
                text_embedding.unsqueeze(0)
            )
            scores[label] = similarity.item()

        # Sort by score descending
        sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return sorted_scores

    def classify_room(self, image_source, threshold: float = 0.2) -> Tuple[Optional[str], float]:
        """
        Classify the room type of an interior image.

        Args:
            image_source: Path, URL, or PIL Image
            threshold: Minimum confidence threshold

        Returns:
            Tuple of (room_type, confidence) or (None, 0) if below threshold
        """
        try:
            image = self._load_image(image_source)
            embedding = self._get_image_embedding(image)
            results = self._classify_with_embeddings(embedding, self._room_embeddings)

            top_label, top_score = results[0]

            if top_score >= threshold:
                return top_label, top_score
            return 'other', top_score

        except Exception as e:
            print(f"Classification error: {e}")
            return None, 0.0

    def classify_style(
        self,
        image_source,
        top_k: int = 3,
        threshold: float = 0.15
    ) -> List[Tuple[str, float]]:
        """
        Classify the interior design style of an image.

        Args:
            image_source: Path, URL, or PIL Image
            top_k: Number of top styles to return
            threshold: Minimum confidence threshold

        Returns:
            List of (style, confidence) tuples
        """
        try:
            image = self._load_image(image_source)
            embedding = self._get_image_embedding(image)
            results = self._classify_with_embeddings(embedding, self._style_embeddings)

            # Filter by threshold and return top_k
            filtered = [(label, score) for label, score in results if score >= threshold]
            return filtered[:top_k]

        except Exception as e:
            print(f"Style classification error: {e}")
            return []

    def classify_full(self, image_source) -> Dict:
        """
        Full classification: room type and styles.

        Returns:
            Dict with room_type, room_confidence, and styles
        """
        try:
            image = self._load_image(image_source)
            embedding = self._get_image_embedding(image)

            room_results = self._classify_with_embeddings(embedding, self._room_embeddings)
            style_results = self._classify_with_embeddings(embedding, self._style_embeddings)

            return {
                'room_type': room_results[0][0],
                'room_confidence': room_results[0][1],
                'room_scores': dict(room_results),
                'styles': [s[0] for s in style_results[:3] if s[1] > 0.15],
                'style_scores': dict(style_results),
            }

        except Exception as e:
            print(f"Full classification error: {e}")
            return {
                'room_type': None,
                'room_confidence': 0,
                'room_scores': {},
                'styles': [],
                'style_scores': {},
            }


# Global classifier instance (lazy-loaded)
_classifier: Optional[CLIPClassifier] = None


def get_classifier() -> CLIPClassifier:
    """Get or create the global CLIP classifier instance."""
    global _classifier
    if _classifier is None:
        _classifier = CLIPClassifier()
    return _classifier


def classify_room_clip(image_source) -> Tuple[Optional[str], float]:
    """
    Convenience function to classify room type.

    Args:
        image_source: Path, URL, or PIL Image

    Returns:
        Tuple of (room_type, confidence)
    """
    classifier = get_classifier()
    return classifier.classify_room(image_source)


def classify_image_full(image_source) -> Dict:
    """
    Convenience function for full classification.

    Args:
        image_source: Path, URL, or PIL Image

    Returns:
        Dict with room_type, styles, and confidence scores
    """
    classifier = get_classifier()
    return classifier.classify_full(image_source)


# Batch classification for efficiency
def classify_batch(
    image_sources: List,
    classify_styles: bool = True
) -> List[Dict]:
    """
    Classify multiple images in batch for efficiency.

    Args:
        image_sources: List of paths, URLs, or PIL Images
        classify_styles: Whether to also classify styles

    Returns:
        List of classification results
    """
    if not HAS_CLIP:
        return [{'room_type': None, 'error': 'CLIP not available'} for _ in image_sources]

    classifier = get_classifier()
    results = []

    for source in image_sources:
        try:
            if classify_styles:
                result = classifier.classify_full(source)
            else:
                room_type, confidence = classifier.classify_room(source)
                result = {'room_type': room_type, 'room_confidence': confidence}
            results.append(result)
        except Exception as e:
            results.append({'room_type': None, 'error': str(e)})

    return results

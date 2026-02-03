"""Bomagi Interior Inspiration Scraper."""
from .database import init_db, get_stats
from .sources import get_source, SOURCES

__version__ = "0.1.0"
__all__ = ['init_db', 'get_stats', 'get_source', 'SOURCES']

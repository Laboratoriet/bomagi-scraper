"""Source adapters for Bomagi scraper."""

# AI image sources
from .civitai import CivitaiSource
from .lexica import LexicaSource
from .midjourney import MidjourneySource

# Real estate
from .finn import FinnSource

# Pinterest
from .pinterest import PinterestSource, PinterestHARSource, PinterestApifySource, PinterestDirectSource

# Scandinavian furniture brands
from .brands import (
    AllBrandsSource,
    BoliaSource,
    HAYSource,
    MuutoSource,
    NormannSource,
    FermLivingSource,
    StringSource,
    MenuSource,
    BoConceptSource,
    IKEASource,
)

# Design magazines
from .magazines import (
    AllMagazinesSource,
    DezeenSource,
    ArchDailySource,
    YellowtraceSource,
    TheNordicroomSource,
    MyScandinavianHomeSource,
    CocoCottonSource,
    ResidenceMagSource,
    BoBedreSource,
)


SOURCES = {
    # === Real interior photography (recommended) ===
    'brands': AllBrandsSource,          # All Scandinavian furniture brands
    'magazines': AllMagazinesSource,    # All design magazines

    # Individual brands
    'bolia': BoliaSource,
    'hay': HAYSource,
    'muuto': MuutoSource,
    'normann': NormannSource,
    'fermliving': FermLivingSource,
    'string': StringSource,
    'menu': MenuSource,
    'boconcept': BoConceptSource,
    'ikea': IKEASource,

    # Individual magazines
    'dezeen': DezeenSource,
    'archdaily': ArchDailySource,
    'yellowtrace': YellowtraceSource,
    'nordroom': TheNordicroomSource,
    'myscandinavianhome': MyScandinavianHomeSource,
    'cocolapine': CocoCottonSource,
    'residence': ResidenceMagSource,
    'bobedre': BoBedreSource,

    # Norwegian real estate
    'finn': FinnSource,

    # Pinterest
    'pinterest': PinterestSource,
    'pinterest_har': PinterestHARSource,
    'pinterest_apify': PinterestApifySource,
    'pinterest_direct': PinterestDirectSource,

    # === AI sources (less recommended for quality) ===
    'civitai': CivitaiSource,
    'lexica': LexicaSource,
    'midjourney': MidjourneySource,
}


def get_source(name: str, config: dict = None):
    """Get a source adapter by name."""
    if name not in SOURCES:
        raise ValueError(f"Unknown source: {name}. Available: {list(SOURCES.keys())}")
    return SOURCES[name](config)


def list_sources():
    """List all available sources with descriptions."""
    return {
        'brands': 'All Scandinavian furniture brands (Bolia, HAY, IKEA, etc.)',
        'magazines': 'All design magazines (Dezeen, Bo Bedre, etc.)',
        'finn': 'Finn.no Norwegian real estate listings',
        'pinterest': 'Pinterest (requires HAR file)',
        'civitai': 'Civitai AI images (mixed quality)',
        'lexica': 'Lexica.art AI images (mixed quality)',
        'midjourney': 'Midjourney showcase (AI)',
    }

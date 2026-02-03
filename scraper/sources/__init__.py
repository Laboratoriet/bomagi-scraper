"""Source adapters for Bomagi scraper."""

# Simple sources (no Playwright required - recommended!)
from .simple_brands import (
    SIMPLE_SOURCES,
    AllSimpleSourcesCombined,
    DezeenSimpleSource,
    ArchDailySimpleSource,
    NordroomSource,
    CocoLapineSource,
    MyScandinavianHomeSource,
    YellowtraceLightSource,
    DesignMilkSource,
)

# AI image sources
from .civitai import CivitaiSource
from .lexica import LexicaSource
from .midjourney import MidjourneySource

# Real estate
from .finn import FinnSource

# Pinterest
from .pinterest import PinterestSource, PinterestHARSource, PinterestApifySource, PinterestDirectSource

# Playwright-based sources (require: playwright install chromium)
try:
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
    from .magazines import (
        AllMagazinesSource,
        DezeenSource,
        ArchDailySource,
        YellowtraceSource,
        TheNordicroomSource,
        MyScandinavianHomeSource as MagMyScandinavianHomeSource,
        CocoCottonSource,
        ResidenceMagSource,
        BoBedreSource,
    )
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False


# Build sources registry - simple sources first (no Playwright needed)
SOURCES = {
    # === Simple sources (RECOMMENDED - no Playwright required) ===
    'all_simple': AllSimpleSourcesCombined,    # All blogs combined
    'dezeen': DezeenSimpleSource,
    'archdaily': ArchDailySimpleSource,
    'nordroom': NordroomSource,
    'cocolapine': CocoLapineSource,
    'myscandinavianhome': MyScandinavianHomeSource,
    'yellowtrace': YellowtraceLightSource,
    'designmilk': DesignMilkSource,

    # Norwegian real estate (no Playwright)
    'finn': FinnSource,

    # Pinterest (various methods)
    'pinterest': PinterestSource,
    'pinterest_har': PinterestHARSource,
    'pinterest_apify': PinterestApifySource,
    'pinterest_direct': PinterestDirectSource,

    # === AI sources (less recommended for quality) ===
    'civitai': CivitaiSource,
    'lexica': LexicaSource,
    'midjourney': MidjourneySource,
}

# Add Playwright sources if available
if PLAYWRIGHT_AVAILABLE:
    SOURCES.update({
        # Playwright-based brand scrapers
        'brands_pw': AllBrandsSource,
        'bolia': BoliaSource,
        'hay': HAYSource,
        'muuto': MuutoSource,
        'normann': NormannSource,
        'fermliving': FermLivingSource,
        'string': StringSource,
        'menu': MenuSource,
        'boconcept': BoConceptSource,
        'ikea': IKEASource,
        # Playwright-based magazine scrapers
        'magazines_pw': AllMagazinesSource,
        'dezeen_pw': DezeenSource,
        'archdaily_pw': ArchDailySource,
        'yellowtrace_pw': YellowtraceSource,
        'nordroom_pw': TheNordicroomSource,
        'residence': ResidenceMagSource,
        'bobedre': BoBedreSource,
    })


def get_source(name: str, config: dict = None):
    """Get a source adapter by name."""
    if name not in SOURCES:
        raise ValueError(f"Unknown source: {name}. Available: {list(SOURCES.keys())}")

    source_class = SOURCES[name]
    # Some sources don't take config
    try:
        return source_class(config) if config else source_class()
    except TypeError:
        return source_class()


def list_sources():
    """List all available sources with descriptions."""
    sources = {
        'all_simple': 'All design blogs combined (Dezeen, Nordroom, etc.) - NO PLAYWRIGHT REQUIRED',
        'dezeen': 'Dezeen magazine - interiors section',
        'archdaily': 'ArchDaily architecture/interior projects',
        'nordroom': 'The Nordroom - Scandinavian interiors blog',
        'cocolapine': 'Coco Lapine Design blog',
        'myscandinavianhome': 'My Scandinavian Home blog',
        'yellowtrace': 'Yellowtrace design blog',
        'designmilk': 'Design Milk blog',
        'finn': 'Finn.no Norwegian real estate listings',
        'pinterest': 'Pinterest (requires HAR file)',
        'civitai': 'Civitai AI images (mixed quality)',
        'lexica': 'Lexica.art AI images (mixed quality)',
        'midjourney': 'Midjourney showcase (AI)',
    }

    if PLAYWRIGHT_AVAILABLE:
        sources.update({
            'brands_pw': 'All Scandinavian brands (Playwright required)',
            'magazines_pw': 'All magazines (Playwright required)',
        })

    return sources

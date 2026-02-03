"""FastAPI backend for Bomagi scraper."""
import asyncio
from pathlib import Path
from typing import Optional, List
from datetime import datetime

from fastapi import FastAPI, HTTPException, BackgroundTasks, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from scraper.database import (
    init_db, get_images, update_image, get_stats,
    insert_image, image_exists, start_scrape_run, complete_scrape_run
)
from scraper.sources import get_source, SOURCES
from scraper.base import download_image, IMAGES_DIR

app = FastAPI(
    title="Bomagi Interior Scraper",
    description="API for scraping and curating interior design inspiration images",
    version="0.1.0"
)

# CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve downloaded images
if IMAGES_DIR.exists():
    app.mount("/images", StaticFiles(directory=str(IMAGES_DIR)), name="images")


# --- Models ---

class ScrapeRequest(BaseModel):
    source: str
    query: str = "interior design"
    room_type: Optional[str] = None
    limit: int = 50
    download: bool = False  # Whether to download images locally


class CurateRequest(BaseModel):
    status: str  # 'approved' or 'rejected'
    notes: Optional[str] = None


class ImageResponse(BaseModel):
    id: int
    source: str
    source_id: str
    source_url: Optional[str]
    image_url: str
    thumbnail_url: Optional[str]
    title: Optional[str]
    prompt: Optional[str]
    room_type: Optional[str]
    quality_score: Optional[float]
    engagement: Optional[int]
    status: str
    local_path: Optional[str]


# --- Background task for scraping ---

scrape_status = {}

def run_scrape(
    run_id: int,
    source_name: str,
    query: str,
    room_type: str,
    limit: int,
    download: bool
):
    """Background scraping task."""
    scrape_status[run_id] = {"status": "running", "found": 0, "new": 0}

    try:
        source = get_source(source_name)
        found = 0
        new = 0

        for result in source.search(query=query, room_type=room_type, limit=limit):
            found += 1
            scrape_status[run_id]["found"] = found

            # Process and add classification
            result = source.process_result(result)

            # Check if already exists
            if not image_exists(result["source"], result["source_id"]):
                # Download if requested
                if download:
                    local_path = download_image(
                        result["image_url"],
                        result["source"],
                        result["source_id"]
                    )
                    result["local_path"] = local_path

                # Insert into database
                insert_image(result)
                new += 1
                scrape_status[run_id]["new"] = new

        complete_scrape_run(run_id, found, new)
        scrape_status[run_id]["status"] = "completed"

    except Exception as e:
        complete_scrape_run(run_id, found, new, str(e))
        scrape_status[run_id]["status"] = "failed"
        scrape_status[run_id]["error"] = str(e)


# --- Routes ---

@app.on_event("startup")
async def startup():
    """Initialize database on startup."""
    init_db()


@app.get("/")
async def root():
    """API info."""
    return {
        "name": "Bomagi Interior Scraper",
        "version": "0.1.0",
        "sources": list(SOURCES.keys()),
        "room_types": [
            "living_room", "kitchen", "bedroom", "bathroom",
            "hallway", "dining", "office", "outdoor", "other"
        ]
    }


@app.get("/stats")
async def stats():
    """Get database statistics."""
    return get_stats()


@app.post("/scrape")
async def scrape(request: ScrapeRequest, background_tasks: BackgroundTasks):
    """
    Start a scraping job.
    Returns immediately with a run_id to track progress.
    """
    if request.source not in SOURCES:
        raise HTTPException(400, f"Unknown source: {request.source}")

    run_id = start_scrape_run(
        source=request.source,
        query=request.query,
        room_type=request.room_type
    )

    background_tasks.add_task(
        run_scrape,
        run_id,
        request.source,
        request.query,
        request.room_type,
        request.limit,
        request.download
    )

    return {"run_id": run_id, "status": "started"}


@app.get("/scrape/{run_id}")
async def get_scrape_status(run_id: int):
    """Get status of a scraping job."""
    if run_id in scrape_status:
        return scrape_status[run_id]
    return {"status": "unknown"}


@app.get("/images")
async def list_images(
    source: Optional[str] = None,
    room_type: Optional[str] = None,
    status: Optional[str] = Query(None, description="pending, approved, or rejected"),
    min_quality: Optional[float] = Query(None, ge=0, le=1),
    search: Optional[str] = Query(None, description="Search title, prompt, or URL"),
    limit: int = Query(50, le=200),
    offset: int = 0,
    order_by: str = "quality_score DESC"
):
    """List images with optional filters."""
    images = get_images(
        source=source,
        room_type=room_type,
        status=status,
        min_quality=min_quality,
        search=search,
        limit=limit,
        offset=offset,
        order_by=order_by
    )
    return {"images": images, "count": len(images)}


@app.get("/images/{image_id}")
async def get_image(image_id: int):
    """Get single image details."""
    images = get_images(limit=1)  # TODO: add get_by_id
    # Simplified - in production add proper lookup
    raise HTTPException(404, "Image not found")


@app.patch("/images/{image_id}")
async def curate_image(image_id: int, request: CurateRequest):
    """Approve or reject an image."""
    update_image(image_id, {
        "status": request.status,
        "notes": request.notes,
        "curated_at": datetime.now().isoformat()
    })
    return {"id": image_id, "status": request.status}


@app.post("/images/{image_id}/download")
async def download_single_image(image_id: int):
    """Download a single image to local storage."""
    images = get_images(limit=1000)  # Simplified
    for img in images:
        if img["id"] == image_id:
            if img.get("local_path"):
                return {"status": "already_downloaded", "path": img["local_path"]}

            local_path = download_image(
                img["image_url"],
                img["source"],
                img["source_id"]
            )
            if local_path:
                update_image(image_id, {"local_path": local_path})
                return {"status": "downloaded", "path": local_path}
            else:
                raise HTTPException(500, "Download failed")

    raise HTTPException(404, "Image not found")


@app.get("/export")
async def export_approved(room_type: Optional[str] = None):
    """Export approved images as JSON."""
    images = get_images(
        status="approved",
        room_type=room_type,
        limit=10000,
        order_by="room_type, quality_score DESC"
    )
    return {
        "count": len(images),
        "images": images
    }


# --- Run server ---

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

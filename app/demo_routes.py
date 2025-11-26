"""
Demo endpoints for PATAS landing page.
Provides sample data download and async job-based analysis for demo purposes.
"""
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
import os
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

demo_router = APIRouter(prefix="/api/demo", tags=["demo"])

# Path to spam dataset (relative to project root)
SPAM_DATASET_PATH = Path(__file__).parent.parent / "static" / "spam_dataset_1000.csv"


@demo_router.get("/download_test_data")
async def download_test_data():
    """
    Download sample spam dataset for testing the demo.
    Returns a CSV file with 1000 diverse spam messages in multiple languages.
    """
    try:
        if not SPAM_DATASET_PATH.exists():
            logger.error(f"Spam dataset not found at {SPAM_DATASET_PATH}")
            raise HTTPException(
                status_code=404,
                detail="Sample dataset not found. Please contact support."
            )
        
        return FileResponse(
            path=str(SPAM_DATASET_PATH),
            filename="spam_dataset_1000.csv",
            media_type="text/csv"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error serving test data: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to serve test data: {str(e)}"
        )

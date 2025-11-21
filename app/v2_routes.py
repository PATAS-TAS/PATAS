"""
Experimental v2 routes for transmodal features.

NOTE: This module contains EXPERIMENTAL endpoints for future transmodal features
(file/image analysis). These are NOT part of PATAS Core v2 production features.

Status: Experimental/Placeholder - Not implemented
Dependencies: app/mq.py (message queue)

For production use, see app/api/ for the stable PATAS Core v2 API.
"""
from fastapi import APIRouter, UploadFile, File, HTTPException
from typing import Optional
import logging

logger = logging.getLogger(__name__)

# Create empty router - endpoints moved to legacy as they're experimental
v2_router = APIRouter(prefix="/v2", tags=["v2"])

# NOTE: Original file/image analysis endpoints were experimental and not implemented.
# They have been removed. If transmodal features are needed in the future,
# implement them properly as a separate service or in a future v2.1 release.
#
# See legacy/v2_routes_experimental.py for reference.



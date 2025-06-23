"""
Vision Control API - Advanced tracking parameter control
"""

import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# Vision API instance will be set by TrackStudioApp
vision_api = None


def set_vision_api(api):
    """Set the VisionAPI instance to use"""
    global vision_api  # noqa: PLW0603
    vision_api = api
    logger.info(f"🔗 Vision Control API received VisionAPI with {api.tracker.__class__.__name__}")


router = APIRouter()


class ConfigUpdate(BaseModel):
    params: dict[str, Any]


@router.get("/config/schema")
async def get_processor_config_schema():
    """Get the JSON schema for the current vision processor's configuration."""
    if not vision_api:
        raise HTTPException(status_code=503, detail="Vision API not available")

    schema = vision_api.get_config_schema()
    if schema:
        return schema
    raise HTTPException(status_code=404, detail="No processor with configurable parameters found.")


@router.get("/config")
async def get_processor_config():
    """Get the current configuration of the vision processor."""
    if not vision_api:
        raise HTTPException(status_code=503, detail="Vision API not available")

    config = vision_api.get_current_config()
    if config:
        return config
    raise HTTPException(status_code=404, detail="No processor with configuration found.")


@router.post("/config")
async def update_processor_config(update: ConfigUpdate):
    """Update parameters of the current vision processor."""
    if not vision_api:
        raise HTTPException(status_code=503, detail="Vision API not available")

    try:
        vision_api.update_config(update.params)
        return {"message": "Configuration updated successfully."}
    except Exception as e:
        logger.error(f"Error updating processor config: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


class RestartRequest(BaseModel):
    preserve_calibration: bool = True


@router.post("/restart")
async def restart_vision_system(request: RestartRequest):
    """
    Restart the entire vision system with fresh tracker and merger instances.
    This resets all tracking states and reinitializes components with current configuration.
    """
    if not vision_api:
        raise HTTPException(status_code=503, detail="Vision API not available")

    try:
        logger.info(f"🔄 Vision system restart requested (preserve_calibration: {request.preserve_calibration})")
        success = vision_api.restart_vision_system(preserve_calibration=request.preserve_calibration)

        if success:
            return {
                "success": True,
                "message": "Vision system restarted successfully. All tracking states have been reset.",
                "tracker": vision_api.tracker.__class__.__name__,
                "merger": vision_api.merger.__class__.__name__,
                "calibration_preserved": request.preserve_calibration,
            }
        raise HTTPException(status_code=500, detail="Vision system restart failed")

    except Exception as e:
        logger.error(f"Error restarting vision system: {e}")
        raise HTTPException(status_code=500, detail=f"Vision system restart failed: {str(e)}") from e

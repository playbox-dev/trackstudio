"""
Cameras API - Camera management and streaming endpoints

This module handles camera configuration and integrates with the vision package
for computer vision processing.
"""

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..config import ServerConfig
from ..stream_combiner import stream_combiner_manager

logger = logging.getLogger(__name__)
router = APIRouter()

# Vision API instance will be set by TrackStudioApp
vision_api = None


def set_vision_api(api):
    """Set the VisionAPI instance to use"""
    global vision_api  # noqa: PLW0603
    vision_api = api
    logger.info(f"🔗 Cameras API received VisionAPI with {api.tracker.__class__.__name__}")


class CameraInfo(BaseModel):
    """Camera information model"""

    id: int
    name: str
    stream_url: str
    enabled: bool
    status: str = "disconnected"


class CameraConfig(BaseModel):
    """Camera configuration model"""

    name: str | None = None
    enabled: bool | None = None


class StreamDelayRequest(BaseModel):
    """Stream delay configuration request"""

    delay_ms: int


class StreamDelaysRequest(BaseModel):
    """All stream delays configuration request"""

    delays: dict[str, int]  # {"0": delay_ms, "1": delay_ms}


@router.get("/", response_model=list[CameraInfo])
@router.get("", response_model=list[CameraInfo])  # Handle without trailing slash
async def get_cameras():
    """Get list of available cameras"""
    try:
        # Get enabled streams from server config
        enabled_streams = ServerConfig.get_enabled_streams()
        cameras = []

        for stream in enabled_streams:
            camera_info = CameraInfo(
                id=stream["id"],
                name=stream["name"],
                stream_url=stream["url"],
                enabled=stream["enabled"],
                status="available",
            )
            cameras.append(camera_info)

        logger.info(f"Retrieved {len(cameras)} active streams")
        return cameras

    except Exception as e:
        logger.error(f"Error getting cameras: {e}")
        raise HTTPException(status_code=500, detail="Failed to get cameras") from e


@router.get("/config")
async def get_camera_config():
    """Get camera configuration including resolution settings"""
    try:
        resolution_config = ServerConfig.get_camera_resolution()
        camera_list = ServerConfig.get_enabled_streams()

        return {
            "resolution": resolution_config,
            "cameras": camera_list,
            "combined_resolution": {
                "width": resolution_config["combined_width"],
                "height": resolution_config["combined_height"],
            },
            "individual_resolution": {
                "width": resolution_config["individual_width"],
                "height": resolution_config["individual_height"],
            },
        }

    except Exception as e:
        logger.error(f"Error getting camera config: {e}")
        raise HTTPException(status_code=500, detail="Failed to get camera configuration") from e


# Stream delay control endpoints - MUST BE BEFORE /{camera_id} route
@router.get("/stream-delays")
async def get_stream_delays():
    """Get current stream delay settings"""
    try:
        delays = stream_combiner_manager.get_stream_delays()
        logger.info(f"Current stream delays: {delays}")
        return {"delays": delays, "unit": "milliseconds", "status": "success"}
    except Exception as e:
        logger.error(f"Error getting stream delays: {e}")
        raise HTTPException(status_code=500, detail="Failed to get stream delays") from e


@router.put("/stream-delays/{stream_id}")
async def set_stream_delay(stream_id: int, request: StreamDelayRequest):
    """Set delay for a specific stream"""
    try:
        # Validate stream ID against enabled streams
        enabled_streams = ServerConfig.get_enabled_streams()
        valid_stream_ids = [stream["id"] for stream in enabled_streams]

        if stream_id not in valid_stream_ids:
            raise HTTPException(
                status_code=400, detail=f"Invalid stream_id: {stream_id}. Valid IDs: {valid_stream_ids}"
            )

        if request.delay_ms < 0 or request.delay_ms > 5000:
            raise HTTPException(
                status_code=400, detail=f"Invalid delay: {request.delay_ms}ms. Must be between 0 and 5000ms"
            )

        success = await stream_combiner_manager.set_stream_delay(stream_id, request.delay_ms)

        if success:
            logger.info(f"Set stream {stream_id} delay to {request.delay_ms}ms")
            return {
                "message": f"Stream {stream_id} delay set to {request.delay_ms}ms",
                "stream_id": stream_id,
                "delay_ms": request.delay_ms,
                "status": "success",
            }
        raise HTTPException(status_code=500, detail="Failed to apply stream delay")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error setting stream {stream_id} delay: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to set stream delay: {str(e)}") from e


@router.put("/stream-delays")
async def set_all_stream_delays(request: StreamDelaysRequest):
    """Set delays for all streams at once"""
    try:
        # Validate stream IDs and delay values
        enabled_streams = ServerConfig.get_enabled_streams()
        valid_stream_ids = [stream["id"] for stream in enabled_streams]

        for stream_id_str, delay_ms in request.delays.items():
            stream_id = int(stream_id_str)
            if stream_id not in valid_stream_ids:
                raise HTTPException(
                    status_code=400, detail=f"Invalid stream_id: {stream_id}. Valid IDs: {valid_stream_ids}"
                )
            if delay_ms < 0 or delay_ms > 5000:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid delay for stream {stream_id}: {delay_ms}ms. Must be between 0 and 5000ms",
                )

        success = await stream_combiner_manager.set_all_delays(request.delays)

        if success:
            logger.info(f"Set all stream delays: {request.delays}")
            return {"message": "All stream delays updated", "delays": request.delays, "status": "success"}
        raise HTTPException(status_code=500, detail="Failed to apply all stream delays")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error setting all stream delays: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to set stream delays: {str(e)}") from e


@router.get("/{camera_id}", response_model=CameraInfo)
async def get_camera(camera_id: int):
    """Get specific camera information"""
    try:
        # Get stream configuration by ID
        stream_config = ServerConfig.get_stream_by_id(camera_id)
        camera_info = CameraInfo(
            id=stream_config["id"],
            name=stream_config["name"],
            stream_url=stream_config["url"],
            enabled=stream_config["enabled"],
            status="available",
        )

        # Try to get status from vision API if available
        if vision_api and hasattr(vision_api, "get_camera_status"):
            try:
                status = vision_api.get_camera_status(camera_id)
                camera_info.status = status
            except Exception as e:
                logger.warning(f"Error getting camera status from vision: {e}")

        return camera_info

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception as e:
        logger.error(f"Error getting camera {camera_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get camera") from e


@router.put("/{camera_id}/config")
async def update_camera_config(camera_id: int, config: CameraConfig):
    """Update camera configuration"""
    try:
        # Validate stream exists
        ServerConfig.get_stream_by_id(camera_id)

        # Here you would update the camera configuration
        # For now, just return success
        logger.info(f"Updated camera {camera_id} configuration: {config}")

        return {"message": f"Camera {camera_id} configuration updated", "config": config}

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception as e:
        logger.error(f"Error updating camera {camera_id} config: {e}")
        raise HTTPException(status_code=500, detail="Failed to update camera configuration") from e


@router.post("/tracking/start")
async def start_tracking():
    """Start vision tracking for all cameras"""
    try:
        logger.info("📡 API: Received request to start vision tracking")
        print("📡 API: Received request to start vision tracking")

        # Check vision API state before enabling
        print(f"📡 API: Vision API instance: {vision_api}")
        if vision_api:
            print(f"📡 API: Vision tracking before enable: {vision_api.is_tracking_enabled()}")
        else:
            print("📡 API: Vision API not available")

        stream_combiner_manager.enable_vision_tracking()

        # Verify it was enabled
        is_enabled = stream_combiner_manager.is_vision_tracking_enabled()
        logger.info(f"📡 API: Vision tracking enabled: {is_enabled}")
        print(f"📡 API: Vision tracking enabled: {is_enabled}")

        return {"message": "Vision tracking started", "enabled": is_enabled, "status": "success"}
    except Exception as e:
        logger.error(f"❌ API: Error starting vision tracking: {e}")
        print(f"❌ API: Error starting vision tracking: {e}")
        raise HTTPException(status_code=500, detail="Failed to start vision tracking") from e


@router.post("/tracking/stop")
async def stop_tracking():
    """Stop vision tracking for all cameras"""
    try:
        stream_combiner_manager.disable_vision_tracking()
        logger.info("Stopped vision tracking")
        return {"message": "Vision tracking stopped", "enabled": False, "status": "success"}
    except Exception as e:
        logger.error(f"Error stopping vision tracking: {e}")
        raise HTTPException(status_code=500, detail="Failed to stop vision tracking") from e


@router.get("/tracking/status")
async def get_tracking_status():
    """Get current vision tracking status"""
    try:
        is_enabled = stream_combiner_manager.is_vision_tracking_enabled()
        stats = stream_combiner_manager.get_vision_statistics()
        latest_result = stream_combiner_manager.get_latest_vision_result()

        # Get tracker type from VisionAPI
        tracker_type = None
        if vision_api and hasattr(vision_api, "tracker"):
            tracker_type = vision_api.tracker.__class__.__name__

        logger.info(f"📡 API: Tracking status check - enabled: {is_enabled}, tracker: {tracker_type}")
        print(f"📡 API: Tracking status check - enabled: {is_enabled}, tracker: {tracker_type}")

        if latest_result:
            # Count detections from all streams
            total_detections = 0
            if hasattr(latest_result, "all_stream_detections") and latest_result.all_stream_detections:
                total_detections = sum(len(dets) for dets in latest_result.all_stream_detections.values())
            print(f"📡 API: Latest vision result: frame {latest_result.frame_id}, {total_detections} detections")
        else:
            print("📡 API: No vision results available")

        return {
            "enabled": is_enabled,
            "tracker_type": tracker_type,
            "statistics": stats,
            "has_latest_result": latest_result is not None,
            "latest_frame_id": latest_result.frame_id if latest_result else None,
            "status": "success",
        }
    except Exception as e:
        logger.error(f"❌ API: Error getting tracking status: {e}")
        print(f"❌ API: Error getting tracking status: {e}")
        raise HTTPException(status_code=500, detail="Failed to get tracking status") from e


@router.get("/tracking/results")
async def get_tracking_results():
    """Get latest vision tracking results"""
    try:
        vision_result = stream_combiner_manager.get_latest_vision_result()

        logger.info(f"📊 API: Tracking results requested - has result: {vision_result is not None}")
        print(f"📊 API: Tracking results requested - has result: {vision_result is not None} (print)")

        if vision_result is None:
            logger.warning("📊 API: No tracking results available")
            print("📊 API: No tracking results available (print)")
            return {"message": "No tracking results available", "data": None, "status": "no_data"}

        # Count detections and tracks from all streams
        total_detections = 0
        total_tracks = 0
        if hasattr(vision_result, "all_stream_detections") and vision_result.all_stream_detections:
            total_detections = sum(len(dets) for dets in vision_result.all_stream_detections.values())
        if hasattr(vision_result, "all_stream_tracks") and vision_result.all_stream_tracks:
            total_tracks = sum(len(tracks) for tracks in vision_result.all_stream_tracks.values())

        # Log the result details
        logger.info(
            f"📊 API: Sending tracking result - frame {vision_result.frame_id}, "
            f"detections={total_detections}, tracks={total_tracks}, "
            f"BEV={len(vision_result.bev_tracks)}"
        )

        # Convert dataclasses to dictionaries for JSON response
        response_data = {
            "frame_id": vision_result.frame_id,
            "timestamp": vision_result.timestamp,
            "processing_time_ms": vision_result.processing_time_ms,
            "bev_tracks": _aggregate_bev_tracks_for_api(vision_result.bev_tracks),
        }

        # Add multi-stream information from VisionResult
        if vision_result.all_stream_detections and vision_result.all_stream_tracks:
            response_data["num_streams"] = vision_result.num_streams
            response_data["active_stream_ids"] = vision_result.active_stream_ids
            response_data["all_stream_detections"] = {}
            response_data["all_stream_tracks"] = {}

            for stream_id, detections in vision_result.all_stream_detections.items():
                response_data["all_stream_detections"][str(stream_id)] = [
                    {
                        "bbox": det.bbox,
                        "confidence": det.confidence,
                        "class_name": det.class_name,
                        "class_id": det.class_id,
                    }
                    for det in detections
                ]

            for stream_id, tracks in vision_result.all_stream_tracks.items():
                response_data["all_stream_tracks"][str(stream_id)] = [
                    {
                        "track_id": track.track_id,
                        "bbox": track.bbox,
                        "confidence": track.confidence,
                        "age": track.age,
                        "camera_id": track.camera_id,
                    }
                    for track in tracks
                ]

        return {"message": "Latest tracking results", "data": response_data, "status": "success"}
    except Exception as e:
        logger.error(f"Error getting tracking results: {e}")
        raise HTTPException(status_code=500, detail="Failed to get tracking results") from e


def _aggregate_bev_tracks_for_api(bev_tracks):
    """
    Aggregate BEV tracks by global_id for API response.
    Averages positions for tracks with the same global ID.
    """
    # Group tracks by global_id
    global_id_groups = {}
    tracks_without_global_id = []

    for track in bev_tracks:
        global_id = getattr(track, "global_id", None)
        if global_id:
            if global_id not in global_id_groups:
                global_id_groups[global_id] = []
            global_id_groups[global_id].append(track)
        else:
            tracks_without_global_id.append(track)

    # Create aggregated tracks
    aggregated_tracks = []

    # Process tracks with global IDs
    for global_id, track_group in global_id_groups.items():
        if len(track_group) == 1:
            # Single track
            track = track_group[0]
            aggregated_tracks.append(
                {
                    "track_id": f"global_{global_id}",
                    "bev_x": track.bev_x,
                    "bev_y": track.bev_y,
                    "confidence": track.confidence,
                    "camera_id": track.camera_id,
                    "global_id": global_id,
                    "camera_count": 1,
                }
            )
        else:
            # Multiple tracks - average positions
            avg_x = sum(t.bev_x for t in track_group) / len(track_group)
            avg_y = sum(t.bev_y for t in track_group) / len(track_group)
            avg_confidence = sum(t.confidence for t in track_group) / len(track_group)
            camera_ids = [t.camera_id for t in track_group if hasattr(t, "camera_id")]

            aggregated_tracks.append(
                {
                    "track_id": f"global_{global_id}",
                    "bev_x": avg_x,
                    "bev_y": avg_y,
                    "confidence": avg_confidence,
                    "camera_id": camera_ids[0] if camera_ids else None,  # Primary camera
                    "global_id": global_id,
                    "camera_count": len(track_group),
                    "all_cameras": camera_ids,
                }
            )

    # Add tracks without global IDs
    aggregated_tracks.extend(
        [
            {
                "track_id": track.track_id,
                "bev_x": track.bev_x,
                "bev_y": track.bev_y,
                "confidence": track.confidence,
                "camera_id": track.camera_id,
                "global_id": None,
                "camera_count": 1,
            }
            for track in tracks_without_global_id
        ]
    )

    return aggregated_tracks

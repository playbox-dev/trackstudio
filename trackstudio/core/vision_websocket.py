"""
Vision WebSocket - Simple WebSocket for vision metadata transmission
"""

import asyncio
import contextlib
import json
import logging
import time
from typing import Any

import numpy as np
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from .config import ServerConfig
from .stream_combiner import stream_combiner_manager

logger = logging.getLogger(__name__)
router = APIRouter()


def make_json_serializable(obj: Any) -> Any:
    """Convert numpy types and other non-JSON-serializable types to Python native types"""
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.floating):
        return float(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, dict):
        return {key: make_json_serializable(value) for key, value in obj.items()}
    if isinstance(obj, list | tuple):
        return [make_json_serializable(item) for item in obj]
    return obj


class VisionWebSocketManager:
    """Manages WebSocket connections for vision metadata"""

    def __init__(self):
        self.active_connections: set[WebSocket] = set()
        self.transmission_task = None
        self.is_running = False

    async def connect(self, websocket: WebSocket):
        """Accept a new WebSocket connection"""
        await websocket.accept()
        self.active_connections.add(websocket)
        logger.info(f"Vision WebSocket connected. Total connections: {len(self.active_connections)}")

        # Start transmission task if this is the first connection
        if len(self.active_connections) == 1 and not self.is_running:
            await self.start_transmission()

    def disconnect(self, websocket: WebSocket):
        """Remove a WebSocket connection"""
        self.active_connections.discard(websocket)
        logger.info(f"Vision WebSocket disconnected. Total connections: {len(self.active_connections)}")

        # Stop transmission task if no more connections
        if len(self.active_connections) == 0 and self.is_running:
            asyncio.create_task(self.stop_transmission())

    async def start_transmission(self):
        """Start the vision metadata transmission task"""
        if self.is_running:
            return

        self.is_running = True
        self.transmission_task = asyncio.create_task(self._transmission_loop())
        logger.info("Started vision metadata transmission")

    async def stop_transmission(self):
        """Stop the vision metadata transmission task"""
        self.is_running = False
        if self.transmission_task and not self.transmission_task.done():
            self.transmission_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self.transmission_task
        logger.info("Stopped vision metadata transmission")

    async def _transmission_loop(self):
        """High-frequency vision metadata transmission - only send when data changes"""
        last_sent_frame_id = None

        try:
            while self.is_running and self.active_connections:
                try:
                    # Get latest vision results
                    vision_result = stream_combiner_manager.get_latest_vision_result()
                    vision_tracking_enabled = stream_combiner_manager.is_vision_tracking_enabled()

                    # Only send if we have new vision data (different frame ID)
                    should_send_data = False
                    metadata = None

                    if (
                        vision_result is not None
                        and vision_tracking_enabled
                        and vision_result.frame_id != last_sent_frame_id
                    ):
                        should_send_data = True
                        last_sent_frame_id = vision_result.frame_id

                    # Send periodic status even if no vision data (every 5 seconds)
                    elif (
                        vision_tracking_enabled
                        and hasattr(self, "_last_status_time")
                        and (time.time() - self._last_status_time) > 5.0
                    ):
                        should_send_data = True
                        self._last_status_time = time.time()

                        # Create status message
                        metadata = {
                            "type": "vision_status",
                            "timestamp": time.time(),
                            "tracking_enabled": True,
                            "active_stream_ids": [stream["id"] for stream in ServerConfig.get_enabled_streams()],
                            "message": "Vision tracking active, waiting for video frames...",
                        }
                    elif not hasattr(self, "_last_status_time"):
                        self._last_status_time = time.time()

                    if should_send_data and vision_result is not None:
                        # Get active stream information from vision result
                        active_stream_ids = vision_result.active_stream_ids or []
                        all_stream_detections = vision_result.all_stream_detections or {}
                        all_stream_tracks = vision_result.all_stream_tracks or {}

                        # Convert vision result to JSON metadata (with multi-stream support)
                        # Use relative timestamp for frontend correlation if available
                        correlation_timestamp = getattr(vision_result, "relative_timestamp", vision_result.timestamp)

                        metadata = {
                            "type": "vision_metadata",
                            "timestamp": float(vision_result.timestamp),
                            "correlation_timestamp": float(correlation_timestamp),  # For video sync
                            "frame_id": int(vision_result.frame_id),
                            "processing_time_ms": float(vision_result.processing_time_ms),
                            "num_streams": int(vision_result.num_streams),
                            "active_stream_ids": [int(sid) for sid in active_stream_ids],
                            # Multi-stream data
                            "all_streams": {
                                str(stream_id): {
                                    "detections": [
                                        {
                                            "id": i,
                                            "bbox": [float(x) for x in det.bbox],
                                            "confidence": float(det.confidence),
                                            "class_name": str(det.class_name),
                                            "class_id": int(det.class_id),
                                            "bottom_center": [
                                                float(det.bbox[0] + det.bbox[2] / 2),
                                                float(det.bbox[1] + det.bbox[3]),
                                            ],
                                        }
                                        for i, det in enumerate(all_stream_detections.get(stream_id, []))
                                    ],
                                    "tracks": [
                                        {
                                            "id": str(track.track_id),
                                            "bbox": [float(x) for x in track.bbox],
                                            "confidence": float(track.confidence),
                                            "class_name": "person",  # Default for now
                                            "center": [
                                                float((track.bbox[0] + track.bbox[2]) / 2),
                                                float((track.bbox[1] + track.bbox[3]) / 2),
                                            ],
                                        }
                                        for track in all_stream_tracks.get(stream_id, [])
                                    ],
                                }
                                for stream_id in active_stream_ids
                            },
                            "bev_tracks": make_json_serializable(
                                self._aggregate_bev_tracks_by_global_id(vision_result.bev_tracks)
                            ),
                        }

                        # Debug logging
                        sum(len(stream_data) for stream_data in all_stream_detections.values())
                        sum(
                            1
                            for track in vision_result.bev_tracks
                            if hasattr(track, "trajectory") and track.trajectory and len(track.trajectory) > 1
                        )

                        # Send the message (either vision data or status)
                        if metadata:
                            await self.broadcast(metadata)

                    # Sleep for a short time to prevent excessive CPU usage
                    await asyncio.sleep(0.01)  # 100 Hz polling, only send when data changes

                except Exception as e:  # noqa: PERF203
                    logger.error(f"Error in vision transmission loop: {e}")
                    await asyncio.sleep(0.1)  # Shorter wait on error

        except asyncio.CancelledError:
            logger.info("Vision transmission loop cancelled")
        except Exception as e:
            logger.error(f"Vision transmission loop error: {e}")

    async def broadcast(self, message: dict):
        """Send message to all connected clients with minimal latency"""
        if not self.active_connections:
            return

        message_str = json.dumps(message, separators=(",", ":"))  # Compact JSON
        disconnected = set()

        # Send to all clients concurrently for maximum speed
        tasks = []
        for websocket in self.active_connections:
            task = asyncio.create_task(self._send_to_client(websocket, message_str, disconnected))
            tasks.append(task)

        # Wait for all sends to complete
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

        # Remove disconnected clients
        for websocket in disconnected:
            self.disconnect(websocket)

    async def _send_to_client(self, websocket: WebSocket, message_str: str, disconnected: set):
        """Send message to a single client"""
        try:
            await websocket.send_text(message_str)
        except Exception:
            disconnected.add(websocket)

    def _aggregate_bev_tracks_by_global_id(self, bev_tracks):
        """
        Aggregate BEV tracks by global_id, averaging positions for tracks with the same ID.
        This ensures only one point is shown on the BEV view for objects tracked by multiple cameras.
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
                # Keep tracks without global IDs as-is
                tracks_without_global_id.append(track)

        # Create aggregated tracks
        aggregated_tracks = []

        # Process tracks with global IDs
        for global_id, track_group in global_id_groups.items():
            if len(track_group) == 1:
                # Single track, use as-is
                track = track_group[0]
                aggregated_tracks.append(
                    {
                        "id": f"global_{global_id}",  # Use global ID as the primary ID
                        "position": [track.bev_x, track.bev_y],
                        "velocity": [0, 0],  # TODO: Calculate velocity
                        "confidence": track.confidence,
                        "class_name": "person",  # Default for now
                        "global_id": global_id,
                        "trajectory": track.trajectory
                        if hasattr(track, "trajectory") and track.trajectory is not None
                        else [],
                        "cameras": [track.camera_id] if hasattr(track, "camera_id") else [],
                        "source": "single_camera",
                    }
                )
            else:
                # Multiple tracks with same global ID - average their positions
                avg_x = sum(t.bev_x for t in track_group) / len(track_group)
                avg_y = sum(t.bev_y for t in track_group) / len(track_group)
                avg_confidence = sum(t.confidence for t in track_group) / len(track_group)

                # Use the trajectory from the first track (they should be the same)
                trajectory = None
                for track in track_group:
                    if hasattr(track, "trajectory") and track.trajectory:
                        trajectory = track.trajectory
                        break

                # Collect all camera IDs
                camera_ids = []
                camera_ids = [track.camera_id for track in track_group if hasattr(track, "camera_id")]

                aggregated_tracks.append(
                    {
                        "id": f"global_{global_id}",  # Use global ID as the primary ID
                        "position": [avg_x, avg_y],
                        "velocity": [0, 0],  # TODO: Calculate velocity
                        "confidence": avg_confidence,
                        "class_name": "person",  # Default for now
                        "global_id": global_id,
                        "trajectory": trajectory if trajectory is not None else [],
                        "cameras": camera_ids,
                        "source": "multi_camera",
                    }
                )

        # Add tracks without global IDs
        aggregated_tracks.extend(
            [
                {
                    "id": track.track_id,
                    "position": [track.bev_x, track.bev_y],
                    "velocity": [0, 0],  # TODO: Calculate velocity
                    "confidence": track.confidence,
                    "class_name": "person",  # Default for now
                    "global_id": None,
                    "trajectory": track.trajectory
                    if hasattr(track, "trajectory") and track.trajectory is not None
                    else [],
                    "cameras": [track.camera_id] if hasattr(track, "camera_id") else [],
                    "source": "no_global_id",
                }
                for track in tracks_without_global_id
            ]
        )

        return aggregated_tracks


# Global manager instance
vision_manager = VisionWebSocketManager()


@router.websocket("/vision-metadata")
async def vision_websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for vision metadata"""
    try:
        await vision_manager.connect(websocket)

        # Keep connection alive and handle client messages (if any)
        while True:
            try:
                # We don't expect messages from client, but we need to keep the loop alive
                await websocket.receive_text()
                # Ignore client messages for now
            except WebSocketDisconnect:  # noqa: PERF203
                break
            except Exception as e:  # noqa: PERF203
                logger.warning(f"Vision WebSocket error: {e}")
                break

    except WebSocketDisconnect:
        logger.info("Vision WebSocket disconnected normally")
    except Exception as e:
        logger.error(f"Vision WebSocket error: {e}")
    finally:
        vision_manager.disconnect(websocket)

"""
Server Configuration Settings
"""

import os
from typing import Any


class ServerConfig:
    """Server-specific configuration"""

    # Server Settings - use SERVER_IP environment variable
    SERVER_IP = os.getenv("SERVER_IP", "localhost")
    SERVER_NAME = os.getenv("SERVER_NAME", "localhost")
    SERVER_PORT = int(os.getenv("SERVER_PORT", "8002"))
    SERVER_RELOAD = os.getenv("SERVER_RELOAD", "true").lower() == "true"

    # CORS Settings - include both localhost and SERVER_IP
    CORS_ORIGINS = [
        "http://localhost:5174",  # Vite dev server
        "http://localhost:3000",  # Alternative dev server
        f"http://{SERVER_IP}:3000",
        f"http://{SERVER_IP}:5173",
        f"http://{SERVER_IP}:5174",
    ]

    # Add localhost variants if SERVER_IP is different
    if SERVER_IP != "localhost":
        CORS_ORIGINS.extend(["http://127.0.0.1:3000", "http://127.0.0.1:5173", "http://127.0.0.1:5174"])

    # WebRTC Settings
    STUN_SERVERS = ["stun:stun.l.google.com:19302", "stun:stun1.l.google.com:19302", "stun:stun2.l.google.com:19302"]

    # WebRTC Connection Timeouts (prevent ICE transaction issues)
    WEBRTC_TIMEOUTS = {
        "answer_timeout": 20.0,  # Increased from 15s for multi-stream
        "ice_timeout": 30.0,  # ICE gathering timeout
        "connection_timeout": 45.0,  # Overall connection timeout
        "close_timeout": 5.0,  # Peer connection close timeout
    }

    # Integration with Vision Package - use SERVER_IP for stream URLs
    VISION_API_ENABLED = True
    STREAM_SERVER_URL = f"rtmp://{SERVER_IP}:1936"  # Default RTMP server for backward compatibility
    STREAM_STAT_URL = f"http://{SERVER_IP}:8085/stat"  # Stream statistics URL

    # Camera Resolution Configuration
    CAMERA_RESOLUTION = {
        "individual_width": int(os.getenv("CAMERA_WIDTH", "720")),
        "individual_height": int(os.getenv("CAMERA_HEIGHT", "480")),
        "combined_width": int(os.getenv("COMBINED_WIDTH", "1440")),
        "combined_height": int(os.getenv("COMBINED_HEIGHT", "480")),
        "fps": int(os.getenv("CAMERA_FPS", "15")),
    }

    # BEV Coordinate System Configuration
    # Adjust these to match your real-world calibration scale
    BEV_CONFIG = {
        "calibration_canvas_size": int(os.getenv("BEV_CANVAS_SIZE", "600")),  # Calibration canvas size (pixels)
        "real_world_area_meters": float(os.getenv("BEV_AREA_METERS", "12.0")),  # Real world area represented (meters)
        "max_coordinate_range": float(os.getenv("BEV_MAX_RANGE", "10.0")),  # Maximum coordinate range (±meters)
    }

    # Stream Configuration (Configurable RTMP/RTSP streams, max 4)
    STREAM_CONFIG = {
        "max_streams": 4,
        "active_streams": int(os.getenv("NUM_STREAMS", "2")),  # Number of active streams (1-4)
        "layout_mode": os.getenv("LAYOUT_MODE", "auto"),  # auto, grid, horizontal, vertical
    }

    # Stream Sources Configuration (RTMP/RTSP with codec specification)
    STREAM_SOURCES = [
        {
            "id": 0,
            "name": os.getenv("STREAM_0_NAME", "Stream 0"),
            "type": os.getenv("STREAM_0_TYPE", "rtmp"),  # rtmp or rtsp
            "url": os.getenv("STREAM_0_URL", f"{STREAM_SERVER_URL}/live/stream0"),
            "codec": os.getenv("STREAM_0_CODEC", "h264"),  # h264, h265, mjpeg, auto
            "enabled": os.getenv("STREAM_0_ENABLED", "true").lower() == "true",
            "position": {"x": 0, "y": 0},  # Grid position for layout
        },
        {
            "id": 1,
            "name": os.getenv("STREAM_1_NAME", "Stream 1"),
            "type": os.getenv("STREAM_1_TYPE", "rtmp"),  # rtmp or rtsp
            "url": os.getenv("STREAM_1_URL", f"{STREAM_SERVER_URL}/live/stream1"),
            "codec": os.getenv("STREAM_1_CODEC", "h264"),  # h264, h265, mjpeg, auto
            "enabled": os.getenv("STREAM_1_ENABLED", "true").lower() == "true",
            "position": {"x": 1, "y": 0},  # Grid position for layout
        },
        {
            "id": 2,
            "name": os.getenv("STREAM_2_NAME", "Stream 2"),
            "type": os.getenv("STREAM_2_TYPE", "rtsp"),  # rtmp or rtsp
            "url": os.getenv("STREAM_2_URL", "rtsp://192.168.1.100:554/stream"),
            "codec": os.getenv("STREAM_2_CODEC", "h264"),  # h264, h265, mjpeg, auto
            "enabled": os.getenv("STREAM_2_ENABLED", "false").lower() == "true",
            "position": {"x": 0, "y": 1},  # Grid position for layout
        },
        {
            "id": 3,
            "name": os.getenv("STREAM_3_NAME", "Stream 3"),
            "type": os.getenv("STREAM_3_TYPE", "rtsp"),  # rtmp or rtsp
            "url": os.getenv("STREAM_3_URL", "rtsp://192.168.1.101:554/stream"),
            "codec": os.getenv("STREAM_3_CODEC", "h264"),  # h264, h265, mjpeg, auto
            "enabled": os.getenv("STREAM_3_ENABLED", "false").lower() == "true",
            "position": {"x": 1, "y": 1},  # Grid position for layout
        },
    ]

    # Helper methods for stream configuration
    @classmethod
    def get_enabled_streams(cls) -> list[dict[str, Any]]:
        """Get list of enabled streams"""
        enabled = [stream for stream in cls.STREAM_SOURCES if stream["enabled"]]
        # Limit to active_streams count
        return enabled[: cls.STREAM_CONFIG["active_streams"]]

    @classmethod
    def get_active_stream_count(cls) -> int:
        """Get number of active streams"""
        return min(cls.STREAM_CONFIG["active_streams"], len([s for s in cls.STREAM_SOURCES if s["enabled"]]))

    @classmethod
    def get_stream_by_id(cls, stream_id: int) -> dict[str, Any]:
        """Get stream configuration by ID"""
        for stream in cls.STREAM_SOURCES:
            if stream["id"] == stream_id:
                return stream
        raise ValueError(f"Stream {stream_id} not found in configuration")

    # Legacy camera compatibility (for backward compatibility)
    @classmethod
    def get_default_cameras(cls) -> list[dict[str, Any]]:
        """Build legacy camera list from stream sources"""
        return [
            {
                "id": stream["id"],
                "name": stream["name"],
                "stream_url": stream["url"],
                "enabled": stream["enabled"],
                "resolution": {
                    "width": cls.CAMERA_RESOLUTION["individual_width"],
                    "height": cls.CAMERA_RESOLUTION["individual_height"],
                    "fps": cls.CAMERA_RESOLUTION["fps"],
                },
            }
            for stream in cls.get_enabled_streams()
        ]

    # Initialize DEFAULT_CAMERAS dynamically for backward compatibility
    DEFAULT_CAMERAS = []  # Will be populated dynamically

    @classmethod
    def _update_default_cameras(cls):
        """Update DEFAULT_CAMERAS list dynamically"""
        cls.DEFAULT_CAMERAS = cls.get_default_cameras()

    @classmethod
    def get_camera_config(cls, camera_id: int) -> dict[str, Any]:
        """Get configuration for a specific camera"""
        # Update DEFAULT_CAMERAS if needed
        if not cls.DEFAULT_CAMERAS:
            cls._update_default_cameras()

        for camera in cls.DEFAULT_CAMERAS:
            if camera["id"] == camera_id:
                return camera
        raise ValueError(f"Camera {camera_id} not found in configuration")

    @classmethod
    def get_camera_resolution(cls) -> dict[str, Any]:
        """Get camera resolution configuration"""
        return cls.CAMERA_RESOLUTION.copy()

    @classmethod
    def get_combined_resolution(cls) -> tuple[int, int]:
        """Get combined stream resolution (width, height)"""
        return (cls.CAMERA_RESOLUTION["combined_width"], cls.CAMERA_RESOLUTION["combined_height"])

    @classmethod
    def get_individual_resolution(cls) -> tuple[int, int]:
        """Get individual camera resolution (width, height)"""
        return (cls.CAMERA_RESOLUTION["individual_width"], cls.CAMERA_RESOLUTION["individual_height"])

    @classmethod
    def get_stream_url(cls, stream_name: str) -> str:
        """Get stream URL for a specific stream (RTMP by default)"""
        return f"{cls.STREAM_SERVER_URL}/live/{stream_name}"

    @classmethod
    def get_rtsp_url(cls, stream_name: str) -> str:
        """Get RTSP URL for a specific stream (legacy method for backward compatibility)"""
        return cls.get_stream_url(stream_name)

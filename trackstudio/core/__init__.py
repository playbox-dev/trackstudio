"""
TrackStudio Core Module

Core functionality for TrackStudio including app, config, and stream management.
"""

from .app import app as fastapi_app
from .config import ServerConfig
from .stream_combiner import StreamCombinerTrack, stream_combiner_manager
from .vision_api import VisionAPI, create_vision_api, get_vision_api
from .vision_websocket import VisionWebSocketManager

__all__ = [
    "fastapi_app",
    "ServerConfig",
    "stream_combiner_manager",
    "StreamCombinerTrack",
    "VisionAPI",
    "get_vision_api",
    "create_vision_api",
    "VisionWebSocketManager",
]

"""
Server Configuration Settings
"""

import os
import json # Added import for json
import logging # Added import for logging
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional 


# Initialize logger for this module
logger = logging.getLogger(__name__)

class ServerConfig:
    """
    Server-specific configuration settings for TrackStudio.
    Configuration can be sourced from environment variables, defaults,
    and a loaded JSON configuration file. CLI arguments will then override these.
    """
    
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
        f"http://{SERVER_IP}:5174"
    ]
    
    # Add localhost variants if SERVER_IP is different
    if SERVER_IP != "localhost":
        CORS_ORIGINS.extend([
            "http://127.0.0.1:3000",
            "http://127.0.0.1:5173", 
            "http://127.0.0.1:5174"
        ])
    
    # WebRTC Settings
    STUN_SERVERS = [
        "stun:stun.l.google.com:19302",
        "stun:stun1.l.google.com:19302",
        "stun:stun2.l.google.com:19302"
    ]
    
    # WebRTC Connection Timeouts (prevent ICE transaction issues)
    WEBRTC_TIMEOUTS = {
        "answer_timeout": 20.0,  # Increased from 15s for multi-stream
        "ice_timeout": 30.0,     # ICE gathering timeout
        "connection_timeout": 45.0,  # Overall connection timeout
        "close_timeout": 5.0     # Peer connection close timeout
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
        "fps": int(os.getenv("CAMERA_FPS", "15"))
    }
    
    # BEV Coordinate System Configuration  
    # Adjust these to match your real-world calibration scale
    BEV_CONFIG = {
        "calibration_canvas_size": int(os.getenv("BEV_CANVAS_SIZE", "600")),     # Calibration canvas size (pixels)
        "real_world_area_meters": float(os.getenv("BEV_AREA_METERS", "12.0")), # Real world area represented (meters)
        "max_coordinate_range": float(os.getenv("BEV_MAX_RANGE", "10.0"))       # Maximum coordinate range (±meters)
    }
    
    # Stream Configuration (Configurable RTMP/RTSP streams, max 4)
    STREAM_CONFIG = {
        "max_streams": 4,
        "active_streams": int(os.getenv("NUM_STREAMS", "2")),   # Number of active streams (1-4)
        "layout_mode": os.getenv("LAYOUT_MODE", "auto"),   # auto, grid, horizontal, vertical
    }
    
    # Stream Sources Configuration (RTMP/RTSP with codec specification)
    STREAM_SOURCES = [
        {
            "id": 0,
            "name": os.getenv("STREAM_0_NAME", "Stream 0"),
            "type": os.getenv("STREAM_0_TYPE", "rtmp"),   # rtmp or rtsp
            "url": os.getenv("STREAM_0_URL", f"{STREAM_SERVER_URL}/live/stream0"),
            "codec": os.getenv("STREAM_0_CODEC", "h264"),   # h264, h265, mjpeg, auto
            "enabled": os.getenv("STREAM_0_ENABLED", "true").lower() == "true",
            "position": {"x": 0, "y": 0}   # Grid position for layout
        },
        {
            "id": 1,
            "name": os.getenv("STREAM_1_NAME", "Stream 1"), 
            "type": os.getenv("STREAM_1_TYPE", "rtmp"),   # rtmp or rtsp
            "url": os.getenv("STREAM_1_URL", f"{STREAM_SERVER_URL}/live/stream1"),
            "codec": os.getenv("STREAM_1_CODEC", "h264"),   # h264, h265, mjpeg, auto
            "enabled": os.getenv("STREAM_1_ENABLED", "true").lower() == "true",
            "position": {"x": 1, "y": 0}   # Grid position for layout
        },
        {
            "id": 2,
            "name": os.getenv("STREAM_2_NAME", "Stream 2"),
            "type": os.getenv("STREAM_2_TYPE", "rtsp"),   # rtmp or rtsp   
            "url": os.getenv("STREAM_2_URL", "rtsp://192.168.1.100:554/stream"),
            "codec": os.getenv("STREAM_2_CODEC", "h264"),   # h264, h265, mjpeg, auto
            "enabled": os.getenv("STREAM_2_ENABLED", "false").lower() == "true",
            "position": {"x": 0, "y": 1}   # Grid position for layout
        },
        {
            "id": 3,
            "name": os.getenv("STREAM_3_NAME", "Stream 3"),
            "type": os.getenv("STREAM_3_TYPE", "rtsp"),   # rtmp or rtsp
            "url": os.getenv("STREAM_3_URL", "rtsp://192.168.1.101:554/stream"),
            "codec": os.getenv("STREAM_3_CODEC", "h264"),   # h264, h265, mjpeg, auto
            "enabled": os.getenv("STREAM_3_ENABLED", "false").lower() == "true",
            "position": {"x": 1, "y": 1}   # Grid position for layout
        }
    ]

    # Undistortion settings - now configurable via config file or CLI
    # This default will be overridden by load_config_from_file and then by CLI
    ENABLE_UNDISTORTION = os.getenv("ENABLE_UNDISTORTION", "false").lower() == "true" # Default to false unless explicitly enabled
    
    # NEW: Dictionary to store paths to calibration files, keyed by stream ID
    CALIBRATION_FILES: Dict[int, str] = {} # This will be populated by load_config_from_file or directly by cli.py

    # Internal dictionary to hold raw config data loaded from a JSON file
    _config_data: Dict[str, Any] = {}
    
    @classmethod
    def load_config_from_file(cls, file_path: str):
        """
        Loads configuration from a JSON file into _config_data and applies
        relevant settings to class attributes.
        """
        try:
            with Path(file_path).open('r') as f:
                loaded_data = json.load(f)
                cls._config_data.update(loaded_data) # Update internal config data
            logger.info(f"Loaded server configuration from {file_path}")
            cls._apply_config_data()
        except FileNotFoundError:
            logger.warning(f"Config file not found at {file_path}. Using environment variables and defaults.")
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON in config file: {file_path}. Please check its format.")
        except Exception as e:
            logger.error(f"Error loading config file {file_path}: {e}")

    @classmethod
    def _apply_config_data(cls):
        """
        Applies loaded raw config data from _config_data to relevant class attributes.
        This method is typically called internally after loading a config file.
        """
        # --- Apply general server settings from config file if present ---
        cls.SERVER_IP = cls._config_data.get("server_ip", cls.SERVER_IP)
        cls.SERVER_NAME = cls._config_data.get("server_name", cls.SERVER_NAME)
        cls.SERVER_PORT = cls._config_data.get("server_port", cls.SERVER_PORT)
        # Convert reload string to boolean
        if "server_reload" in cls._config_data:
            cls.SERVER_RELOAD = str(cls._config_data["server_reload"]).lower() == "true"

        # --- Apply Stream Sources from config file if present ---
        # This allows defining streams directly in the config JSON
        if "stream_sources" in cls._config_data and isinstance(cls._config_data["stream_sources"], list):
            # Clear existing default streams and load from config
            cls.STREAM_SOURCES = []
            for stream_entry in cls._config_data["stream_sources"]:
                # Ensure 'enabled' is boolean, and 'id' is int
                if isinstance(stream_entry, dict) and 'id' in stream_entry and 'url' in stream_entry:
                    stream_entry['enabled'] = str(stream_entry.get('enabled', 'true')).lower() == 'true'
                    stream_entry['id'] = int(stream_entry['id'])
                    cls.STREAM_SOURCES.append(stream_entry)
                else:
                    logger.warning(f"Malformed stream entry in config: {stream_entry}. Skipping.")
            logger.info(f"Loaded {len(cls.STREAM_SOURCES)} stream sources from config file.")
        
        # --- Apply Camera Resolution from config file if present ---
        if "camera_resolution" in cls._config_data and isinstance(cls._config_data["camera_resolution"], dict):
            cls.CAMERA_RESOLUTION.update(cls._config_data["camera_resolution"])
            logger.info("Loaded camera resolution from config file.")

        # --- Apply BEV config from config file if present ---
        if "bev_config" in cls._config_data and isinstance(cls._config_data["bev_config"], dict):
            cls.BEV_CONFIG.update(cls._config_data["bev_config"])
            logger.info("Loaded BEV configuration from config file.")

        # --- Apply Stream Config (max_streams, active_streams, layout_mode) from config file if present ---
        if "stream_config" in cls._config_data and isinstance(cls._config_data["stream_config"], dict):
            cls.STREAM_CONFIG.update(cls._config_data["stream_config"])
            # Ensure active_streams is an int and within bounds
            if isinstance(cls.STREAM_CONFIG.get("active_streams"), (str, int)):
                cls.STREAM_CONFIG["active_streams"] = min(int(cls.STREAM_CONFIG["active_streams"]), cls.STREAM_CONFIG["max_streams"])
            logger.info("Loaded stream configuration (max_streams, active_streams, layout_mode) from config file.")


        # --- NEW: Apply ENABLE_UNDISTORTION from config file ---
        if "enable_undistortion" in cls._config_data:
            cls.ENABLE_UNDISTORTION = str(cls._config_data["enable_undistortion"]).lower() == "true"
            logger.info(f"ENABLE_UNDISTORTION set to {cls.ENABLE_UNDISTORTION} from config.")
        
        # --- NEW: Apply CALIBRATION_FILES from config file ---
        if "calibration_files" in cls._config_data and isinstance(cls._config_data["calibration_files"], dict):
            # Convert keys to integers as stream IDs are integers
            cls.CALIBRATION_FILES = {
                int(k): v for k, v in cls._config_data["calibration_files"].items()
            }
            logger.info(f"CALIBRATION_FILES loaded from config: {cls.CALIBRATION_FILES}")
        else:
            cls.CALIBRATION_FILES = {} # Ensure it's empty if not found or malformed
            if "calibration_files" in cls._config_data:
                logger.warning("Config file's 'calibration_files' is not a dictionary or malformed, ignoring it.")

        # --- For backward compatibility with simpler config structures: ---
        # If 'rtsp_streams' and 'camera_names' are in the main _config_data,
        # ensure they are handled by get_enabled_streams.
        # These are used as a fallback if STREAM_SOURCES is not explicitly defined in the config.
        # The cli.py will set these directly if --streams is used.
        # No explicit processing needed here for _config_data["rtsp_streams"] and _config_data["camera_names"]
        # as get_enabled_streams accesses them directly from _config_data.


    # Helper methods for stream configuration
    @classmethod
    def get_enabled_streams(cls) -> List[Dict[str, Any]]:
        """
        Get list of enabled streams based on STREAM_SOURCES.
        Prioritizes streams from STREAM_SOURCES with 'enabled: true'.
        If STREAM_SOURCES is not configured, it tries to use 'rtsp_streams' and 'camera_names' from _config_data.
        """
        # If STREAM_SOURCES were loaded or are defined, use them as primary source
        if cls.STREAM_SOURCES:
            enabled_from_sources = [stream for stream in cls.STREAM_SOURCES if stream.get("enabled", False)]
            # Limit to active_streams count, ensure order if position is used
            # For simplicity, we just limit by count, not specific positions here.
            return enabled_from_sources[:cls.STREAM_CONFIG["active_streams"]]
        
        # Fallback for older config styles that use "rtsp_streams" and "camera_names"
        # This branch is primarily for when STREAM_SOURCES is not defined in the config file.
        streams = []
        rtsp_urls = cls._config_data.get("rtsp_streams")
        camera_names = cls._config_data.get("camera_names")

        if rtsp_urls and isinstance(rtsp_urls, list):
            for i, url in enumerate(rtsp_urls):
                stream_name = f"Camera {i}"
                if camera_names and i < len(camera_names) and isinstance(camera_names[i], str):
                    stream_name = camera_names[i]
                
                # Check if stream is implicitly enabled (e.g., within active_streams limit)
                # For this fallback, all streams in rtsp_urls are considered "enabled" up to active_streams limit
                if i < cls.STREAM_CONFIG["active_streams"]:
                    streams.append({
                        "id": i,
                        "name": stream_name,
                        "type": "rtsp", # Assume RTSP for this fallback structure
                        "url": url,
                        "codec": "h264", # Assume H264 for this fallback
                        "enabled": True,
                        "position": {"x": i % 2, "y": i // 2} # Simple grid position
                    })
        return streams
    
    @classmethod  
    def get_active_stream_count(cls) -> int:
        """Get number of active streams configured to be used."""
        return len(cls.get_enabled_streams()) # Calculated from the result of get_enabled_streams
            
    @classmethod
    def get_stream_by_id(cls, stream_id: int) -> Optional[Dict[str, Any]]:
        """Get stream configuration by ID from STREAM_SOURCES."""
        for stream in cls.STREAM_SOURCES:
            if stream["id"] == stream_id:
                return stream
        logger.warning(f"Stream {stream_id} not found in STREAM_SOURCES configuration.")
        return None
    
    # Legacy camera compatibility (for backward compatibility)
    # This builds a list of "cameras" from the enabled streams.
    @classmethod
    def get_default_cameras(cls) -> List[Dict[str, Any]]:
        """Build legacy camera list from enabled stream sources for backward compatibility."""
        return [
            {
                "id": stream["id"],
                "name": stream["name"],
                "stream_url": stream["url"], 
                "enabled": stream["enabled"],
                "resolution": {
                    "width": cls.CAMERA_RESOLUTION["individual_width"],
                    "height": cls.CAMERA_RESOLUTION["individual_height"],
                    "fps": cls.CAMERA_RESOLUTION["fps"]
                }
            } for stream in cls.get_enabled_streams() # Uses the modern get_enabled_streams now
        ]
    
    # Initialize DEFAULT_CAMERAS dynamically when the class is loaded for first time.
    # This ensures it's always up-to-date with initial config.
    DEFAULT_CAMERAS: List[Dict[str, Any]] = [] # Placeholder

    
    @classmethod
    def _update_default_cameras(cls):
        """Force update of DEFAULT_CAMERAS list dynamically."""
        cls.DEFAULT_CAMERAS = cls.get_default_cameras()
    
    @classmethod
    def get_camera_config(cls, camera_id: int) -> Dict[str, Any]:
        """Get configuration for a specific camera from the DEFAULT_CAMERAS list."""
        # Ensure DEFAULT_CAMERAS is populated (e.g., after loading config)
        if not cls.DEFAULT_CAMERAS:
            cls._update_default_cameras()
            
        for camera in cls.DEFAULT_CAMERAS:
            if camera["id"] == camera_id:
                return camera
        raise ValueError(f"Camera {camera_id} not found in configuration's DEFAULT_CAMERAS.")
    
    @classmethod
    def get_camera_resolution(cls) -> Dict[str, Any]:
        """Get camera resolution configuration."""
        return cls.CAMERA_RESOLUTION.copy()
    
    @classmethod
    def get_combined_resolution(cls) -> Tuple[int, int]:
        """Get combined stream resolution (width, height)."""
        return (cls.CAMERA_RESOLUTION["combined_width"], cls.CAMERA_RESOLUTION["combined_height"])
    
    @classmethod
    def get_individual_resolution(cls) -> Tuple[int, int]:
        """Get individual camera resolution (width, height)."""
        return (cls.CAMERA_RESOLUTION["individual_width"], cls.CAMERA_RESOLUTION["individual_height"])
    
    @classmethod
    def get_stream_url(cls, stream_name: str) -> str:
        """Get stream URL for a specific stream (RTMP by default for legacy)."""
        return f"{cls.STREAM_SERVER_URL}/live/{stream_name}"
    
    @classmethod 
    def get_rtsp_url(cls, stream_name: str) -> str:
        """Get RTSP URL for a specific stream (legacy method for backward compatibility)."""
        # This is a legacy method. Ideally, streams should be configured directly in STREAM_SOURCES
        # with their specific URL and type.
        logger.warning("Using legacy get_rtsp_url. Configure streams directly in STREAM_SOURCES for better control.")
        return cls.get_stream_url(stream_name)
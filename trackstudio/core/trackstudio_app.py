"""
TrackStudio Application

Main application class that coordinates all TrackStudio components.
"""

import asyncio
import logging
import threading
import webbrowser
from collections.abc import Callable
from pathlib import Path
from typing import Any

import uvicorn

from .config import ServerConfig
from .stream_combiner import stream_combiner_manager
from .vision_api import create_vision_api

logger = logging.getLogger(__name__)


class TrackStudioApp:
    """Main TrackStudio application class"""

    def __init__(self, config: "TrackStudioConfig"):
        self.config = config
        self.server = None
        self.server_thread = None
        self.is_running = False
        self._on_track_callback = None

        # Configure the system
        self._configure()

    def _configure(self):
        """Configure the system based on config"""
        # Update server config
        ServerConfig.SERVER_NAME = self.config.server_name
        ServerConfig.SERVER_PORT = self.config.server_port

        # Configure streams
        if self.config.rtsp_streams:
            # Create stream configuration
            streams = []
            for i, url in enumerate(self.config.rtsp_streams):
                name = self.config.camera_names[i] if i < len(self.config.camera_names) else f"Camera {i}"
                streams.append({"id": i, "url": url, "name": name, "enabled": True})

            # Update server config directly
            ServerConfig.STREAM_SOURCES = streams[:4]  # Limit to max 4 streams
            ServerConfig.STREAM_CONFIG["active_streams"] = min(len(streams), 4)
            print(f"📡 Configured {len(streams)} streams for TrackStudio")

        # Configure vision - create the VisionAPI instance
        logger.info(f"🔧 Creating VisionAPI with tracker_type='{self.config.tracker_type}'")
        self.vision_api = create_vision_api(
            tracker_type=self.config.tracker_type,
            merger_type=self.config.merger_type,
            calibration_file=self.config.calibration_file,
        )
        self.vision_api.set_vision_fps(self.config.vision_fps)
        logger.info(f"🧠 VisionAPI created with {self.vision_api.tracker.__class__.__name__}")

        # Pass the VisionAPI instance to all components that need it
        logger.info("🔗 Setting VisionAPI for stream combiner...")
        stream_combiner_manager.set_vision_api(self.vision_api)

        # Set the VisionAPI instance for all API modules
        logger.info("🔗 Setting VisionAPI for API modules...")
        from .api import calibration, cameras, vision_control  # noqa: PLC0415

        calibration.set_vision_api(self.vision_api)
        vision_control.set_vision_api(self.vision_api)
        cameras.set_vision_api(self.vision_api)

        logger.info(f"✅ Configured VisionAPI with {self.vision_api.tracker.__class__.__name__}")

        # Load calibration data if available
        if self.config.calibration_file and Path(self.config.calibration_file).exists():
            try:
                import json  # noqa: PLC0415

                with Path(self.config.calibration_file).open() as f:
                    calibration_data = json.load(f)

                for camera_key, cam_data in calibration_data.items():
                    if camera_key.startswith("camera") and "homography_matrix" in cam_data:
                        camera_id = int(camera_key.replace("camera", ""))
                        # Convert list back to numpy array
                        import numpy as np  # noqa: PLC0415

                        homography_matrix = np.array(cam_data["homography_matrix"])
                        self.vision_api.update_homography(camera_id, homography_matrix)
                        logger.info(f"📊 Loaded homography for camera {camera_id}")
            except Exception as e:
                logger.error(f"Error loading calibration data: {e}")

        # Import the FastAPI app
        from .app import app  # noqa: PLC0415

        # Create server config (but don't start server yet - this is just setup)
        logger.info("🚀 Configuring TrackStudio server...")
        self.server_config = uvicorn.Config(
            app, host=self.config.server_name, port=self.config.server_port, log_level="info"
        )

        # Determine URL for browser opening
        share_mode = getattr(self.config, "share", False)
        if share_mode:
            # Open browser for remote access
            url = f"http://{self.config.server_name}:{self.config.server_port}"
        else:
            # Open browser for local access
            url = f"http://127.0.0.1:{self.config.server_port}"

        logger.info(f"🚀 TrackStudio will be available at {url}")

        # Store the URL for later use
        self.server_url = url

    def start(self):
        """Start the TrackStudio server"""
        if self.is_running:
            logger.warning("TrackStudio is already running")
            return

        # Create server from config
        self.server = uvicorn.Server(self.server_config)

        # Start server in background thread
        self.server_thread = threading.Thread(target=self._run_server, daemon=True)
        self.server_thread.start()
        self.is_running = True

        # Give server time to start
        import time  # noqa: PLC0415

        time.sleep(2)

        # Open browser if not disabled
        if not getattr(self.config, "no_browser", False):
            webbrowser.open(self.server_url)

        logger.info(f"✅ TrackStudio started at {self.server_url}")
        print(f"\n🚀 TrackStudio is running at {self.server_url}")

    def _run_server(self):
        """Run the FastAPI server"""
        # Set up event loop for thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        # Run server (server was already created in start() method)
        loop.run_until_complete(self.server.serve())

    def stop(self):
        """Stop the TrackStudio server"""
        if not self.is_running:
            return

        logger.info("Stopping TrackStudio...")

        # Stop stream combiner
        if stream_combiner_manager.is_running:
            asyncio.run(stream_combiner_manager.stop())

        # Stop server
        if self.server:
            self.server.should_exit = True

        self.is_running = False
        logger.info("✅ TrackStudio stopped")

    def wait(self):
        """Wait for the application to finish"""
        try:
            while self.is_running:
                import time  # noqa: PLC0415

                time.sleep(1)
        except KeyboardInterrupt:
            self.stop()

    def get_local_url(self) -> str:
        """Get the local URL for the server"""
        return f"http://{self.config.server_name}:{self.config.server_port}"

    def create_share_link(self) -> str:
        """Create a public URL using ngrok or similar service"""
        # TODO: Implement ngrok integration
        logger.warning("Share link feature not yet implemented")
        return self.get_local_url()

    def get_latest_tracks(self) -> Any | None:
        """Get the latest tracking results"""
        result = stream_combiner_manager.get_latest_vision_result()
        if result:
            return result.bev_tracks
        return None

    def get_statistics(self) -> dict[str, Any]:
        """Get system statistics"""
        return {
            "stream": stream_combiner_manager.get_stats(),
            "vision": self.vision_api.get_statistics() if hasattr(self, "vision_api") else {},
        }

    def on_track(self, callback: Callable):
        """Set a callback for track events"""
        self._on_track_callback = callback
        # TODO: Implement callback system
        logger.info("Track callback registered")

    def enable_tracking(self):
        """Enable vision tracking"""
        stream_combiner_manager.enable_vision_tracking()

    def disable_tracking(self):
        """Disable vision tracking"""
        stream_combiner_manager.disable_vision_tracking()


class TrackStudioConfig:
    """Configuration for TrackStudio"""

    def __init__(
        self,
        rtsp_streams: list[str],
        camera_names: list[str] | None = None,
        tracker_type: str = "rfdetr",
        merger_type: str = "bev_cluster",
        vision_fps: float = 10.0,
        server_name: str = "127.0.0.1",
        server_port: int = 8000,
        rtsp_server: str | None = None,
        calibration_file: str | None = None,
        share: bool = False,
        no_browser: bool = False,
        **kwargs,
    ):
        self.rtsp_streams = rtsp_streams
        self.camera_names = camera_names or []
        self.tracker_type = tracker_type
        self.merger_type = merger_type
        self.vision_fps = vision_fps
        self.server_name = server_name
        self.server_port = server_port
        self.rtsp_server = rtsp_server
        self.calibration_file = calibration_file
        self.share = share
        self.no_browser = no_browser
        self.extra_config = kwargs

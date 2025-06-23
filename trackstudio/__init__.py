"""
TrackStudio - Multi-Camera Vision Tracking System

Simple API for multi-camera tracking with WebRTC streaming.

Example:
    import trackstudio as ts

    # Launch with default settings
    app = ts.launch(
        rtsp_streams=[
            "rtsp://localhost:8554/camera0",
            "rtsp://localhost:8554/camera1"
        ],
        tracker="rfdetr",  # or "dummy" for testing
        share=True  # Create public URL
    )
"""

__version__ = "0.1.0"

import logging
from collections.abc import Callable
from typing import Any

# Core imports
from .core.trackstudio_app import TrackStudioApp, TrackStudioConfig
from .mergers import merger_registry
from .mergers.base import VisionMerger

# Registry imports
from .trackers import tracker_registry
from .trackers.base import VisionTracker

# Export main classes and functions
__all__ = [
    "launch",
    "TrackStudioApp",
    "TrackStudioConfig",
    "VisionTracker",
    "VisionMerger",
    "register_tracker",
    "register_merger",
    "list_trackers",
    "list_mergers",
]

logger = logging.getLogger(__name__)


def launch(
    rtsp_streams: list[str] | None = None,
    camera_names: list[str] | None = None,
    tracker: str = "rfdetr",
    merger: str = "bev_cluster",
    vision_fps: float = 10.0,
    server_name: str = "127.0.0.1",
    server_port: int = 8000,
    share: bool = False,
    open_browser: bool = True,
    rtsp_server: str | None = None,
    calibration_file: str | None = None,
    config: dict[str, Any] | None = None,
    on_track: Callable | None = None,
    **_kwargs,
) -> TrackStudioApp:
    """
    Launch TrackStudio multi-camera tracking interface.

    Args:
        rtsp_streams: List of RTSP stream URLs to process
        camera_names: Optional names for each camera
        tracker: Vision tracker to use ("rfdetr", "dummy", or custom)
        merger: Cross-camera merger to use ("bev_cluster" or custom)
        vision_fps: Vision processing FPS (default: 10.0)
        server_name: Server hostname (default: "127.0.0.1")
        server_port: Server port (default: 8000)
        share: Create a public URL using ngrok
        open_browser: Automatically open browser
        rtsp_server: Optional external RTSP server URL
        calibration_file: Path to calibration data JSON
        config: Additional configuration options
        on_track: Callback function for track events
        **_kwargs: Additional keyword arguments

    Returns:
        TrackStudioApp instance

    Example:
        >>> import trackstudio as ts
        >>> app = ts.launch(
        ...     rtsp_streams=["rtsp://localhost:8554/cam0"],
        ...     tracker="rfdetr",
        ...     share=True
        ... )
    """
    # Set up default streams if none provided
    if rtsp_streams is None:
        rtsp_streams = ["rtsp://localhost:8554/camera0", "rtsp://localhost:8554/camera1"]

    # Generate camera names if not provided
    if camera_names is None:
        camera_names = [f"Camera {i}" for i in range(len(rtsp_streams))]

    # Create configuration
    app_config = TrackStudioConfig(
        rtsp_streams=rtsp_streams,
        camera_names=camera_names,
        tracker_type=tracker,
        merger_type=merger,
        vision_fps=vision_fps,
        server_name=server_name,
        server_port=server_port,
        rtsp_server=rtsp_server,
        calibration_file=calibration_file,
        share=share,
        no_browser=not open_browser,  # Invert open_browser to get no_browser
        **(config or {}),
    )

    # Create and configure app
    app = TrackStudioApp(app_config)

    # Set callback if provided
    if on_track:
        app.on_track(on_track)

    # Launch the app
    try:
        # Start the server (handles browser opening internally)
        app.start()

        # Create public URL if requested
        if share:
            public_url = app.create_share_link()
            print(f"\n🌐 Public URL: {public_url}")

        print("\n✨ TrackStudio is running!")
        print("Press Ctrl+C to stop.\n")

        return app

    except Exception as e:
        logger.error(f"Failed to launch TrackStudio: {e}")
        raise


def register_tracker(name: str, tracker_class: type):
    """
    Register a custom vision tracker.

    Args:
        name: Name for the tracker
        tracker_class: Tracker class (must inherit from VisionTracker)

    Example:
        >>> from trackstudio import VisionTracker, register_tracker
        >>>
        >>> class MyTracker(VisionTracker):
        ...     def detect(self, frame, camera_id):
        ...         # Custom detection logic
        ...         return []
        >>>
        >>> register_tracker("mytracker", MyTracker)
    """
    tracker_registry.register(name, tracker_class)
    logger.info(f"✅ Registered tracker: {name}")


def register_merger(name: str, merger_class: type):
    """
    Register a custom cross-camera merger.

    Args:
        name: Name for the merger
        merger_class: Merger class (must inherit from VisionMerger)
    """
    merger_registry.register(name, merger_class)
    logger.info(f"✅ Registered merger: {name}")


def list_trackers() -> list[str]:
    """Get list of available vision trackers."""
    return tracker_registry.list_available()


def list_mergers() -> list[str]:
    """Get list of available cross-camera mergers."""
    return merger_registry.list_available()


# Convenience function for quick testing
def demo():
    """Launch TrackStudio with demo configuration."""
    print("🎬 Launching TrackStudio demo...")
    print("Make sure you have RTSP streams running on:")
    print("  - rtsp://localhost:8554/camera0")
    print("  - rtsp://localhost:8554/camera1")
    print()

    return launch(
        rtsp_streams=["rtsp://localhost:8554/camera0", "rtsp://localhost:8554/camera1"],
        camera_names=["Front Camera", "Side Camera"],
        tracker="dummy",  # Use dummy tracker for demo
        open_browser=True,
    )

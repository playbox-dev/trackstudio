"""
TrackStudio Tracker Registry

Dynamic registration system for vision trackers.
"""

import logging

from .base import BEVTrack, Detection, Track, VisionResult, VisionTracker
from .dummy import DummyVisionTracker as DummyTracker
from .rfdetr import RFDETRTracker

logger = logging.getLogger(__name__)


class TrackerRegistry:
    """Registry for vision trackers"""

    def __init__(self):
        self._trackers: dict[str, type[VisionTracker]] = {}
        self._register_defaults()

    def _register_defaults(self):
        """Register default trackers"""
        self.register("rfdetr", RFDETRTracker)
        self.register("dummy", DummyTracker)

    def register(self, name: str, tracker_class: type[VisionTracker]):
        """Register a new tracker"""
        if not issubclass(tracker_class, VisionTracker):
            raise ValueError(f"{tracker_class} must inherit from VisionTracker")

        self._trackers[name] = tracker_class
        logger.info(f"Registered tracker: {name}")

    def get(self, name: str) -> type[VisionTracker]:
        """Get a tracker class by name"""
        if name not in self._trackers:
            raise ValueError(f"Unknown tracker: {name}. Available: {list(self._trackers.keys())}")
        return self._trackers[name]

    def create(self, name: str, **kwargs) -> VisionTracker:
        """Create a tracker instance"""
        tracker_class = self.get(name)
        return tracker_class(**kwargs)

    def list_available(self) -> list[str]:
        """List available tracker names"""
        return list(self._trackers.keys())


# Global registry instance
tracker_registry = TrackerRegistry()

# Export commonly used items
__all__ = [
    "VisionTracker",
    "VisionResult",
    "Detection",
    "Track",
    "BEVTrack",
    "RFDETRTracker",
    "DummyTracker",
    "tracker_registry",
]

"""
TrackStudio Merger Registry

Dynamic registration system for cross-camera track mergers.
"""

import logging

from .base import VisionMerger
from .bev_cluster import BEVClusterMerger

logger = logging.getLogger(__name__)


class MergerRegistry:
    """Registry for vision mergers"""

    def __init__(self):
        self._mergers: dict[str, type[VisionMerger]] = {}
        self._register_defaults()

    def _register_defaults(self):
        """Register default mergers"""
        self.register("bev_cluster", BEVClusterMerger)

    def register(self, name: str, merger_class: type[VisionMerger]):
        """Register a new merger"""
        if not issubclass(merger_class, VisionMerger):
            raise ValueError(f"{merger_class} must inherit from VisionMerger")

        self._mergers[name] = merger_class
        logger.info(f"Registered merger: {name}")

    def get(self, name: str) -> type[VisionMerger]:
        """Get a merger class by name"""
        if name not in self._mergers:
            raise ValueError(f"Unknown merger: {name}. Available: {list(self._mergers.keys())}")
        return self._mergers[name]

    def create(self, name: str, **kwargs) -> VisionMerger:
        """Create a merger instance"""
        merger_class = self.get(name)
        return merger_class(**kwargs)

    def list_available(self) -> list[str]:
        """List available merger names"""
        return list(self._mergers.keys())


# Global registry instance
merger_registry = MergerRegistry()

# Export commonly used items
__all__ = ["VisionMerger", "BEVClusterMerger", "merger_registry"]

"""
Base Vision Merger

This module defines the abstract base class for cross-camera tracking algorithms.
A merger processes BEV tracks from multiple camera trackers to create unified global tracks.
"""

from abc import ABC, abstractmethod
from typing import Any

import numpy as np

from trackstudio.trackers.base import BEVTrack


class VisionMerger(ABC):
    """
    Abstract base class for cross-camera tracking algorithms.

    This class defines the standard interface for processing Bird's Eye View (BEV)
    tracks from multiple camera trackers to generate unified global tracks across
    the entire multi-camera system.

    The merger is responsible for:
    1. Associating tracks from different cameras that represent the same object
    2. Assigning global IDs that persist across camera boundaries
    3. Maintaining trajectory histories for smooth tracking
    4. Resolving conflicts when multiple cameras track the same object

    Attributes:
        Subclasses should define their own attributes as needed for the specific
        merging algorithm (e.g., distance thresholds, feature extractors, etc.)
    """

    def __init__(self) -> None:
        """
        Initialize the vision merger.

        Subclasses should call this constructor and initialize their own
        specific attributes as needed.
        """
        super().__init__()

    @abstractmethod
    def merge(
        self,
        bev_tracks: list[BEVTrack],
        timestamp: float,
        stream_frames: dict[int, np.ndarray] | None = None,
        reid_features: dict[str, np.ndarray] | None = None,
    ) -> list[BEVTrack]:
        """
        Merge BEV tracks from multiple sources to create unified tracks.

        This is the core method that processes tracks from all cameras and
        creates a unified view with global track IDs. The method should handle
        track association, ID assignment, and trajectory management.

        Args:
            bev_tracks: List of BEVTrack objects from all camera streams
            timestamp: Current frame timestamp in seconds
            stream_frames: Optional dictionary mapping camera_id to full video frame
            reid_features: Optional dictionary mapping track_id to ReID feature vector

        Returns:
            List of BEVTrack objects with global IDs assigned and trajectories updated

        Raises:
            ValueError: If input data is invalid or inconsistent
            RuntimeError: If the merging algorithm encounters an internal error
        """
        pass

    @abstractmethod
    def get_statistics(self) -> dict[str, Any]:
        """
        Get statistics about the cross-camera merging process.

        Provides metrics and statistics about the merger's performance,
        including track counts, association rates, and processing times.
        This information is useful for monitoring and debugging the system.

        Returns:
            Dictionary containing merger-specific statistics and metrics.
            Common keys might include:
            - 'total_tracks': Total number of tracks processed
            - 'global_tracks': Number of global tracks maintained
            - 'associations_per_frame': Number of track associations made
            - 'processing_time_ms': Processing time in milliseconds

        Raises:
            RuntimeError: If statistics cannot be computed
        """
        pass

    def reset(self) -> None:
        """
        Reset the merger state.

        This is an optional method that can be implemented to clear all
        internal state, including track histories and global ID assignments.
        Useful for restarting tracking or handling major scene changes.

        The default implementation does nothing, but subclasses can override
        this to provide specific reset functionality.
        """
        # Default implementation does nothing - subclasses can override
        return

    def get_config_schema(self) -> dict[str, Any]:
        """
        Return the JSON schema for the merger's configuration.

        This is an optional method that can be implemented to provide
        configuration schema information for UI generation and validation.

        Returns:
            Dictionary containing the JSON schema, or empty dict if not implemented
        """
        return {}

    def update_config(self, config_update: dict[str, Any]) -> None:
        """
        Update the merger's configuration.

        This is an optional method that can be implemented to allow
        runtime configuration changes of merger parameters.

        Args:
            config_update: Dictionary of configuration parameters to update

        Raises:
            ValueError: If invalid configuration parameters are provided
        """
        # Default implementation does nothing - subclasses can override if needed
        return

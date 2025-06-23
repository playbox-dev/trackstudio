"""
Dummy Vision Tracker

This module implements a dummy tracker for testing and development purposes.
It generates random detections and simple track associations without real
object detection or tracking algorithms.
"""

import logging
from typing import Any

import numpy as np

from .base import BaseTrackerConfig, BEVTrack, Detection, Track, VisionTracker

logger = logging.getLogger(__name__)


class DummyVisionTracker(VisionTracker):
    """
    Default vision tracker with dummy implementations.

    This tracker is used for testing and development. It generates random
    detections and assigns simple track IDs without using actual computer
    vision algorithms.
    """

    def __init__(self, config: BaseTrackerConfig | None = None, calibration_file: str | None = None) -> None:
        """
        Initialize the dummy vision tracker.

        Args:
            config: Optional configuration object (unused by dummy tracker)
            calibration_file: Optional path to calibration data file
        """
        super().__init__(config or BaseTrackerConfig(), calibration_file)
        logger.info("🤖 DummyVisionTracker initialized with dummy detection/tracking")

    def get_config_schema(self) -> dict[str, Any]:
        """
        Return the JSON schema for the tracker's configuration.

        Returns:
            Empty dictionary since dummy tracker has no configuration
        """
        return {}

    def update_config(self, config_update: dict[str, Any]) -> None:
        """
        Update the tracker's configuration.

        Args:
            config_update: Configuration updates (ignored by dummy tracker)
        """
        logger.info("Dummy tracker has no config to update.")
        pass

    def detect(self, frame: np.ndarray, camera_id: int) -> list[Detection]:
        """
        Dummy detection - generates random detections.

        Creates 0-3 random bounding boxes with person class labels
        for testing purposes.

        Args:
            frame: Input image frame
            camera_id: Camera identifier

        Returns:
            List of randomly generated Detection objects
        """
        detections = []

        # Generate 1-3 random detections per frame
        num_detections = np.random.randint(0, 4)

        h, w = frame.shape[:2]

        for _i in range(num_detections):
            # Random bounding box
            x = np.random.randint(0, w - 100)
            y = np.random.randint(0, h - 100)
            width = np.random.randint(50, 150)
            height = np.random.randint(80, 200)

            detection = Detection(
                bbox=(x, y, width, height),
                confidence=0.7 + np.random.random() * 0.3,  # 0.7-1.0
                class_name="person",
                class_id=0,
            )
            detections.append(detection)

        return detections

    def track(
        self, detections: list[Detection], camera_id: int, timestamp: float, frame: np.ndarray | None = None
    ) -> list[Track]:
        """
        Dummy tracking - assigns track IDs to detections.

        Creates simple track IDs based on detection order and timestamp,
        without maintaining track history or identity.

        Args:
            detections: List of detections from current frame
            camera_id: Camera identifier
            timestamp: Current frame timestamp
            frame: Optional frame image (unused)

        Returns:
            List of Track objects with simple IDs
        """
        tracks = []

        for i, detection in enumerate(detections):
            track_id = f"cam{camera_id}_track_{i}_{int(timestamp)}"

            track = Track(
                track_id=track_id,
                bbox=detection.bbox,
                confidence=detection.confidence,
                age=1,  # Dummy age
                camera_id=camera_id,
            )
            tracks.append(track)

        return tracks

    def transform_to_bev(self, tracks: list[Track]) -> list[BEVTrack]:
        """
        Transform tracks to Bird's Eye View coordinates using homography.

        Uses the calibration system to transform track positions from
        camera coordinates to bird's eye view coordinates.

        Args:
            tracks: List of tracks in camera coordinates

        Returns:
            List of BEVTrack objects in bird's eye view coordinates
        """
        bev_tracks = []

        # Debug logging for multi-camera BEV transformation
        camera_track_counts: dict[int, int] = {}
        for track in tracks:
            camera_track_counts[track.camera_id] = camera_track_counts.get(track.camera_id, 0) + 1
        logger.debug(f"🗺️ BEV Transform input: {camera_track_counts} tracks per camera")

        for track in tracks:
            # Use bottom center of bounding box (feet position)
            x, y, w, h = track.bbox
            feet_x = x + w // 2
            feet_y = y + h

            # Use BEV pixels directly instead of converting to meters
            transformed_points = self.calibration.transform_points_to_bev([(feet_x, feet_y)], track.camera_id)

            if not transformed_points:
                logger.debug(f"❌ Camera {track.camera_id} track {track.track_id}: No homography matrix available")
                continue

            bev_x_pixels, bev_y_pixels = transformed_points[0]

            logger.debug(
                f"🗺️ Camera {track.camera_id} track {track.track_id}: "
                f"feet({feet_x},{feet_y}) -> BEV({bev_x_pixels:.1f},{bev_y_pixels:.1f})"
            )

            bev_track = BEVTrack(
                track_id=track.track_id,
                bev_x=bev_x_pixels,
                bev_y=bev_y_pixels,
                confidence=track.confidence,
                camera_id=track.camera_id,
            )
            bev_tracks.append(bev_track)

        logger.debug(f"🗺️ BEV Transform output: {len(bev_tracks)} total BEV tracks")
        return bev_tracks

    def get_statistics(self) -> dict[str, Any]:
        """
        Return tracker statistics.

        Returns:
            Dictionary containing basic tracker information
        """
        return {"tracker_type": "Dummy"}

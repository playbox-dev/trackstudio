#!/usr/bin/env python3
"""
Custom Tracker Examples for TrackStudio

This file demonstrates how to create custom trackers using TrackStudio's plugin system.
It focuses on the API structure and interface rather than specific algorithms, making it
easier to understand the framework and adapt for your own implementations.

Usage:
    # Run the basic example
    python custom_tracker_example.py --tracker basic

    # Run the advanced example
    python custom_tracker_example.py --tracker advanced

    # List all available examples
    python custom_tracker_example.py --list

Requirements:
    - TrackStudio: pip install trackstudio
    - NumPy: Usually included with TrackStudio

License: Apache 2.0 (same as TrackStudio)
"""

from typing import Any

import numpy as np

from trackstudio.tracker_factory import register_tracker_class
from trackstudio.trackers.base import BaseTrackerConfig, BEVTrack, Detection, Track, VisionTracker
from trackstudio.vision_config import int_slider_field, register_tracker_config, slider_field


@register_tracker_config("basic_example")
class BasicTrackerConfig(BaseTrackerConfig):
    """
    Configuration for a basic custom tracker.

    This demonstrates the minimum configuration needed for a custom tracker.
    All parameters defined here will automatically appear in the TrackStudio
    web interface with appropriate controls.
    """

    detection_threshold: float = slider_field(
        0.5, 0.1, 0.9, 0.05, "Detection Threshold", "Minimum confidence for detections"
    )

    max_tracks: int = int_slider_field(
        20, 1, 100, 1, "Maximum Tracks", "Maximum number of objects to track simultaneously"
    )


@register_tracker_class("basic_example")
class BasicTracker(VisionTracker):
    """
    Basic custom tracker template.

    This example demonstrates the minimal structure needed for a custom tracker.
    Replace the placeholder implementations with your own detection and tracking algorithms.
    """

    def __init__(self, config: BasicTrackerConfig, calibration_file: str | None = None):
        """
        Initialize your custom tracker.

        Args:
            config: Configuration object with all your parameters
            calibration_file: Optional path to calibration data file
        """
        super().__init__(config, calibration_file)
        self.config = config

        # Initialize your tracker state here
        self.frame_count = 0
        self.active_tracks = {}
        self.next_track_id = 1

        print(f"🤖 BasicTracker initialized with threshold={config.detection_threshold}")

    def detect(self, frame: np.ndarray, camera_id: int) -> list[Detection]:
        """
        Detect objects in a single frame.

        Args:
            frame: Input image as numpy array, shape (height, width, 3), BGR color format
            camera_id: Unique identifier for the camera (0, 1, 2, etc.)

        Returns:
            List of Detection objects, each containing:
            - bbox: Bounding box as (x, y, width, height) tuple
            - confidence: Detection confidence score (0.0 to 1.0)
            - class_name: Object class as string (e.g., "person", "car")
            - class_id: Numeric class identifier (0, 1, 2, etc.)

        Implementation notes:
        - This method is called for every frame, so optimize for speed
        - Use self.config.detection_threshold to filter results
        - Consider camera_id for camera-specific tuning
        """
        return []

        # TODO: Implement your detection algorithm here
        #
        # Example structure:
        # 1. Preprocess frame (resize, convert color space, etc.)
        # 2. Run detection algorithm (ML model, computer vision, etc.)
        # 3. Post-process results (NMS, filtering, etc.)
        # 4. Convert to Detection objects
        #
        # for bbox, confidence, class_info in your_detection_results:
        #     if confidence >= self.config.detection_threshold:
        #         detection = Detection(
        #             bbox=bbox,
        #             confidence=confidence,
        #             class_name=class_info["name"],
        #             class_id=class_info["id"]
        #         )
        #         detections.append(detection)

    def track(
        self, detections: list[Detection], camera_id: int, timestamp: float, frame: np.ndarray = None
    ) -> list[Track]:
        """
        Associate detections with existing tracks and update object identities.

        Args:
            detections: List of Detection objects from detect() method
            camera_id: Camera identifier (same as in detect())
            timestamp: Current frame timestamp in seconds since epoch
            frame: Original frame data (optional, for appearance-based tracking)

        Returns:
            List of Track objects, each containing:
            - track_id: Unique identifier that persists across frames
            - bbox: Current bounding box as (x, y, width, height)
            - confidence: Tracking confidence score (0.0 to 1.0)
            - class_name: Object class name
            - age: Number of frames this track has existed
            - hits: Number of successful detections for this track

        Implementation notes:
        1. Data association: Match detections to existing tracks
        2. Track update: Update matched tracks with new detections
        3. Track creation: Start new tracks for unmatched detections
        4. Track deletion: Remove tracks that haven't been updated
        5. Track management: Limit total tracks, handle occlusions
        """
        tracks = []

        # TODO: Implement your tracking algorithm here
        #
        # Example structure:
        # 1. Predict track positions (if using motion models)
        # 2. Associate detections with existing tracks (distance, appearance, etc.)
        # 3. Update matched tracks
        # 4. Create new tracks for unmatched detections
        # 5. Remove old/lost tracks
        # 6. Apply track limits from config

        # Apply max tracks limit from configuration
        if len(tracks) > self.config.max_tracks:
            tracks = sorted(tracks, key=lambda t: t.confidence, reverse=True)
            tracks = tracks[: self.config.max_tracks]

        self.frame_count += 1
        return tracks

    def get_config_schema(self) -> dict[str, Any]:
        """
        Return the JSON schema for the tracker's configuration.

        This schema is used by the TrackStudio web interface to generate
        the configuration controls automatically.

        Returns:
            Dictionary containing the JSON schema for this tracker's config
        """
        return self.config.model_json_schema()

    def update_config(self, config_update: dict[str, Any]) -> None:
        """
        Update the tracker's configuration with new parameters.

        This method is called when users change parameters in the web interface.
        You can add custom logic here to handle configuration changes.

        Args:
            config_update: Dictionary of configuration parameters to update
        """
        # Update the config object with new values
        for key, value in config_update.items():
            if hasattr(self.config, key):
                setattr(self.config, key, value)

        # TODO: Add any custom logic for handling config changes
        # Example: reinitialize models with new parameters
        # Example: adjust thresholds, reload weights, etc.

    def transform_to_bev(self, tracks: list[Track]) -> list:
        """
        Transform tracks to Bird's Eye View coordinates.

        Uses the calibration system to convert track positions from camera
        coordinates to a common bird's eye view coordinate system.

        Args:
            tracks: List of tracks in camera coordinates

        Returns:
            List of BEVTrack objects in bird's eye view coordinates
        """

        bev_tracks = []

        for track in tracks:
            # Use bottom center of bounding box (feet position)
            x, y, w, h = track.bbox
            feet_x = x + w // 2
            feet_y = y + h

            # Transform to BEV coordinates using calibration
            transformed_points = self.calibration.transform_points_to_bev([(feet_x, feet_y)], track.camera_id)

            if not transformed_points:
                # Skip tracks without valid calibration
                continue

            bev_x_pixels, bev_y_pixels = transformed_points[0]

            bev_track = BEVTrack(
                track_id=track.track_id,
                bev_x=bev_x_pixels,
                bev_y=bev_y_pixels,
                confidence=track.confidence,
                camera_id=track.camera_id,
            )
            bev_tracks.append(bev_track)

        return bev_tracks

    def get_statistics(self) -> dict[str, Any]:
        """
        Return tracker performance statistics.

        This information is displayed in the TrackStudio web interface.

        Returns:
            Dictionary with tracker statistics and metrics
        """
        return {
            "tracker_type": "BasicTracker Template",
            "frames_processed": self.frame_count,
            "active_tracks": len(self.active_tracks),
            "total_tracks_created": self.next_track_id - 1,
            "detection_threshold": self.config.detection_threshold,
            "max_tracks_limit": self.config.max_tracks,
        }

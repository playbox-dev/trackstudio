import time
from typing import Any

import numpy as np
from pydantic import Field

from trackstudio.tracker_factory import register_tracker_class
from trackstudio.trackers.base import BaseTrackerConfig, BEVTrack, Detection, Track, VisionTracker
from trackstudio.vision_config import int_slider_field, register_tracker_config, slider_field


@register_tracker_config("advanced_example")
class AdvancedTrackerConfig(BaseTrackerConfig):
    """
    Configuration for an advanced tracker with comprehensive options.

    This demonstrates sophisticated configuration patterns including
    dropdown selections, grouped parameters, and feature toggles.
    """

    # Algorithm selection
    detection_algorithm: str = Field(
        default="method_a",
        title="Detection Algorithm",
        description="Which detection method to use",
        json_schema_extra={"ui_control": "select", "options": ["method_a", "method_b", "method_c", "custom"]},
    )

    tracking_algorithm: str = Field(
        default="kalman",
        title="Tracking Algorithm",
        description="Which tracking method to use",
        json_schema_extra={"ui_control": "select", "options": ["centroid", "kalman", "particle_filter", "deep_sort"]},
    )

    # Detection parameters
    detection_threshold: float = slider_field(
        0.5, 0.0, 1.0, 0.05, "Detection Confidence", "Minimum confidence score for accepting detections"
    )

    nms_threshold: float = slider_field(
        0.5, 0.1, 0.9, 0.05, "NMS Threshold", "Non-maximum suppression threshold for overlapping detections"
    )

    # Tracking parameters
    max_tracks: int = int_slider_field(50, 1, 200, 1, "Maximum Tracks", "Maximum number of simultaneous tracks")

    track_timeout: int = int_slider_field(30, 5, 100, 5, "Track Timeout", "Frames before removing lost tracks")

    # Advanced features
    use_motion_prediction: bool = Field(
        default=True, title="Motion Prediction", description="Predict track positions between frames"
    )

    use_appearance_features: bool = Field(
        default=False, title="Appearance Features", description="Use visual features for track association"
    )


@register_tracker_class("advanced_example")
class AdvancedTracker(VisionTracker):
    """
    Advanced tracker template with comprehensive features.

    This example demonstrates:
    - Multiple algorithm backends with runtime switching
    - Advanced configuration options and parameter groups
    - Performance monitoring and adaptive behavior
    - Modular design for easy algorithm swapping
    """

    def __init__(self, config: AdvancedTrackerConfig, calibration_file: str | None = None):
        """Initialize the advanced tracker with comprehensive setup."""
        super().__init__(config, calibration_file)
        self.config = config

        # Performance monitoring
        self.frame_count = 0
        self.processing_times = []

        # Tracking state
        self.tracks = {}
        self.next_track_id = 1

        # Initialize algorithm backends based on configuration
        self._init_detection_backend()
        self._init_tracking_backend()

        print("🚀 AdvancedTracker initialized:")
        print(f"   Detection: {config.detection_algorithm}")
        print(f"   Tracking: {config.tracking_algorithm}")
        print(f"   Motion prediction: {config.use_motion_prediction}")

    def _init_detection_backend(self):
        """Initialize the selected detection algorithm."""
        algorithm = self.config.detection_algorithm

        # TODO: Initialize your detection algorithm based on configuration
        #
        # Example structure:
        # if algorithm == "method_a":
        #     self.detector = MethodADetector()
        # elif algorithm == "method_b":
        #     self.detector = MethodBDetector()
        # elif algorithm == "custom":
        #     self.detector = self._load_custom_detector()

        print(f"   Initialized detection backend: {algorithm}")

    def _init_tracking_backend(self):
        """Initialize the selected tracking algorithm."""
        algorithm = self.config.tracking_algorithm

        # TODO: Initialize your tracking algorithm based on configuration
        #
        # Example structure:
        # if algorithm == "kalman":
        #     self.tracker_backend = KalmanTracker()
        # elif algorithm == "particle_filter":
        #     self.tracker_backend = ParticleFilterTracker()

        print(f"   Initialized tracking backend: {algorithm}")

    def detect(self, frame: np.ndarray, camera_id: int) -> list[Detection]:
        """
        Advanced detection with algorithm switching and performance monitoring.

        Args:
            frame: Input image (height, width, 3) BGR format
            camera_id: Camera identifier for multi-camera systems

        Returns:
            List of Detection objects with bounding boxes, confidence scores,
            and class information

        Advanced features:
        - Runtime algorithm switching based on config
        - Performance monitoring and statistics
        - Multi-stage detection pipeline
        """
        start_time = time.time()
        detections = []

        try:
            # TODO: Implement detection based on selected algorithm
            # Use self.config.detection_algorithm to switch between methods
            #
            # Example structure:
            # if self.config.detection_algorithm == "method_a":
            #     detections = self._detect_method_a(frame)
            # elif self.config.detection_algorithm == "method_b":
            #     detections = self._detect_method_b(frame)
            #
            # Apply post-processing:
            # detections = self._apply_nms(detections)
            # detections = self._filter_by_threshold(detections)

            pass  # Placeholder - replace with your detection implementation

            # Performance monitoring
            processing_time = (time.time() - start_time) * 1000  # Convert to ms
            self.processing_times.append(processing_time)

        except Exception as e:
            print(f"❌ Detection error on camera {camera_id}: {e}")

        return detections

    def track(
        self, detections: list[Detection], camera_id: int, timestamp: float, frame: np.ndarray = None
    ) -> list[Track]:
        """
        Advanced tracking with multiple algorithms and features.

        Args:
            detections: Detection objects from current frame
            camera_id: Camera identifier
            timestamp: Frame timestamp for temporal modeling
            frame: Original frame data for appearance features

        Returns:
            List of Track objects with persistent identities

        Advanced features:
        - Motion prediction and state estimation
        - Appearance-based re-identification
        - Multi-hypothesis tracking
        - Track quality assessment
        """
        tracks = []

        try:
            # TODO: Implement advanced tracking features
            #
            # Motion prediction step
            # if self.config.use_motion_prediction:
            #     self._predict_track_positions(timestamp)

            # Extract appearance features if enabled
            # appearance_features = None
            # if self.config.use_appearance_features and frame is not None:
            #     appearance_features = self._extract_features(frame, detections)

            # Data association with multiple cues
            # associations = self._associate_detections_to_tracks(
            #     detections, camera_id, appearance_features
            # )

            # Update tracks and manage lifecycle
            # tracks = self._update_tracks(associations, timestamp)
            # self._manage_tracks(timestamp)

            pass  # Placeholder - replace with your tracking implementation

        except Exception as e:
            print(f"❌ Tracking error on camera {camera_id}: {e}")

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
        # Example: switch detection/tracking backends based on new algorithm selection

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
        """Return comprehensive performance statistics."""
        avg_processing_time = np.mean(self.processing_times) if self.processing_times else 0

        return {
            "tracker_type": f"AdvancedTracker ({self.config.detection_algorithm} + {self.config.tracking_algorithm})",
            "frames_processed": self.frame_count,
            "active_tracks": len(self.tracks),
            # Algorithm configuration
            "detection_algorithm": self.config.detection_algorithm,
            "tracking_algorithm": self.config.tracking_algorithm,
            # Performance metrics
            "avg_processing_time_ms": round(avg_processing_time, 2),
            # Feature flags
            "motion_prediction": self.config.use_motion_prediction,
            "appearance_features": self.config.use_appearance_features,
            # Tuning parameters
            "detection_threshold": self.config.detection_threshold,
            "nms_threshold": self.config.nms_threshold,
            "track_timeout": self.config.track_timeout,
        }

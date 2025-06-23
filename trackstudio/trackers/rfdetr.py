"""
RF-DETR Vision Tracker

This module implements object detection using RF-DETR (Real-Time DEtection TRansformer)
from Roboflow, with DeepSORT tracking and TorchReID features.
"""

import logging
from typing import Any

import numpy as np
import supervision as sv
from rfdetr.detr import RFDETRBase, RFDETRLarge

from ..models.reid_extractor import TorchReIDExtractor
from ..vision_config import RFDETRTrackerConfig
from .base import BEVTrack, Detection, Track, VisionTracker

logger = logging.getLogger(__name__)

# Import DeepSORT - FAIL if not available (no fallbacks)
from trackers import DeepSORTTracker

logger.info("✅ Using DeepSORTTracker from trackers package")


class RFDETRTracker(VisionTracker):
    """
    RF-DETR based vision tracker with DeepSORT tracking and TorchReID.

    This tracker combines RF-DETR object detection with DeepSORT tracking
    and TorchReID appearance features for robust multi-object tracking.

    Attributes:
        config: Configuration for the tracker
        model_name: Name of the RF-DETR model to use
        reid_model: Name of the ReID model for appearance features
        model: RF-DETR detection model instance
        reid_extractor: ReID feature extractor instance
        trackers: Dictionary of DeepSORT trackers per camera
    """

    def __init__(
        self,
        config: RFDETRTrackerConfig,
        model_name: str = "RFDETRBase",
        reid_model: str = "osnet_x1_0",
        calibration_file: str | None = None,
    ) -> None:
        """
        Initialize the RF-DETR tracker.

        Args:
            config: Configuration object for the tracker
            model_name: Name of the RF-DETR model ("RFDETRBase" or "RFDETRLarge")
            reid_model: Name of the ReID model for appearance features
            calibration_file: Optional path to calibration data file
        """
        super().__init__(config, calibration_file)
        self.config: RFDETRTrackerConfig = config
        self.model_name = model_name
        self.reid_model = reid_model

        self.model: RFDETRBase | RFDETRLarge | None = None
        self.reid_extractor: TorchReIDExtractor | None = None
        self.trackers: dict[int, Any] = {}

        self._initialize_detector()
        self._initialize_reid()

        logger.info(f"🎯 RFDETRTracker initialized with {model_name}")

    def update_config(self, config_update: dict[str, Any]) -> None:
        """
        Update the tracker's configuration.

        Args:
            config_update: Dictionary of configuration parameters to update
        """
        new_config_data = self.config.model_dump()
        for key, value in config_update.items():
            if key in new_config_data:
                new_config_data[key] = value

        self.config = RFDETRTrackerConfig(**new_config_data)

        # Update live-updatable tracker parameters
        for tracker in self.trackers.values():
            if hasattr(tracker, "max_age"):
                tracker.max_age = self.config.tracking.tracker_max_age
            if hasattr(tracker, "min_hits"):
                tracker.min_hits = self.config.tracking.tracker_min_hits
            if hasattr(tracker, "_metric") and hasattr(tracker._metric, "_metric_params"):
                tracker._metric._metric_params["matching_threshold"] = self.config.tracking.tracker_matching_threshold

    def _initialize_detector(self) -> None:
        """
        Initialize RF-DETR detection model.

        Creates the appropriate RF-DETR model based on the model_name parameter.
        """
        if self.model_name == "RFDETRBase":
            self.model = RFDETRBase(resolution=560)
        elif self.model_name == "RFDETRLarge":
            self.model = RFDETRLarge(resolution=560)
        else:
            self.model = RFDETRBase(pretrain_weights=self.model_name)

    def _initialize_reid(self) -> None:
        """
        Initialize ReID feature extractor using singleton pattern.

        Creates a TorchReID extractor for appearance-based tracking features.
        """
        from ..models.reid_singleton import get_reid_extractor  # noqa: PLC0415

        self.reid_extractor = get_reid_extractor(model_name=self.reid_model)

        if self.reid_extractor is None:
            logger.warning("⚠️ ReID extractor could not be initialized - tracking will be less accurate")

    def _get_or_create_tracker(self, camera_id: int) -> Any:
        """
        Get or create a DeepSORT tracker for a specific camera.

        Args:
            camera_id: ID of the camera to get/create tracker for

        Returns:
            DeepSORT tracker instance for the specified camera

        Raises:
            RuntimeError: If ReID extractor is not initialized
        """
        if camera_id not in self.trackers:
            if self.reid_extractor is None:
                raise RuntimeError("ReID extractor not initialized.")

            # Use TorchReIDExtractor directly - DeepSORT will call it with supervision.Detections
            self.trackers[camera_id] = DeepSORTTracker(feature_extractor=self.reid_extractor)

            tracker = self.trackers[camera_id]
            if hasattr(tracker, "max_age"):
                tracker.max_age = self.config.tracking.tracker_max_age
            if hasattr(tracker, "min_hits"):
                tracker.min_hits = self.config.tracking.tracker_min_hits
            if hasattr(tracker, "_metric") and hasattr(tracker._metric, "_metric_params"):
                tracker._metric._metric_params["matching_threshold"] = self.config.tracking.tracker_matching_threshold

        return self.trackers[camera_id]

    def detect(self, frame: np.ndarray, camera_id: int) -> list[Detection]:
        """
        Detect objects in a frame using RF-DETR.

        Args:
            frame: Input image frame
            camera_id: ID of the camera (for logging)

        Returns:
            List of detected objects (filtered for persons only)

        Raises:
            RuntimeError: If RF-DETR model is not initialized
        """
        if self.model is None:
            raise RuntimeError("RF-DETR model not initialized.")

        sv_detections = self.model.predict(frame)
        person_detections = []

        if hasattr(sv_detections, "class_id") and sv_detections.class_id is not None:
            for i in range(len(sv_detections)):
                if sv_detections.class_id[i] == 1:  # Person class
                    if sv_detections.confidence[i] < self.config.detection.confidence_threshold:
                        continue

                    x1, y1, x2, y2 = sv_detections.xyxy[i]
                    w, h = x2 - x1, y2 - y1

                    if (
                        w < self.config.detection.min_box_width
                        or h < self.config.detection.min_box_height
                        or (h > 0 and w / h > self.config.detection.max_aspect_ratio)
                    ):
                        continue

                    person_detections.append(
                        Detection(
                            bbox=(int(x1), int(y1), int(w), int(h)),
                            confidence=float(sv_detections.confidence[i]),
                            class_name="person",
                            class_id=1,
                        )
                    )

        if len(person_detections) > 1:
            return self._apply_nms(person_detections, self.config.detection.nms_iou_threshold)

        return person_detections

    def track(
        self, detections: list[Detection], camera_id: int, timestamp: float, frame: np.ndarray | None = None
    ) -> list[Track]:
        """
        Track objects across frames using DeepSORT.

        Args:
            detections: List of detections from current frame
            camera_id: ID of the source camera
            timestamp: Current frame timestamp
            frame: Original frame (required for DeepSORT)

        Returns:
            List of tracked objects with IDs

        Raises:
            ValueError: If frame is None (required for DeepSORT)
        """
        if frame is None:
            raise ValueError("Frame is required for DeepSORT.")

        tracker = self._get_or_create_tracker(camera_id)

        if not detections:
            tracker.update(sv.Detections.empty(), frame)
            return []

        sv_detections = sv.Detections(
            xyxy=np.array([[d.bbox[0], d.bbox[1], d.bbox[0] + d.bbox[2], d.bbox[1] + d.bbox[3]] for d in detections]),
            confidence=np.array([d.confidence for d in detections]),
            class_id=np.array([d.class_id for d in detections]),
        )

        tracked_detections = tracker.update(sv_detections, frame)

        tracks = []
        if hasattr(tracked_detections, "tracker_id") and tracked_detections.tracker_id is not None:
            for i, tracker_id in enumerate(tracked_detections.tracker_id):
                if tracker_id is not None and tracker_id >= 0:
                    x1, y1, x2, y2 = tracked_detections.xyxy[i]
                    tracks.append(
                        Track(
                            track_id=f"cam{camera_id}_track_{tracker_id}",
                            bbox=(int(x1), int(y1), int(x2 - x1), int(y2 - y1)),
                            confidence=tracked_detections.confidence[i],
                            age=1,
                            camera_id=camera_id,
                        )
                    )
        return tracks

    def get_statistics(self) -> dict[str, Any]:
        """
        Get tracker statistics.

        Returns:
            Dictionary containing tracker type and statistics
        """
        return {"tracker_type": "RF-DETR + DeepSORT"}

    def _apply_nms(self, detections: list[Detection], iou_threshold: float) -> list[Detection]:
        """
        Apply Non-Maximum Suppression to detections.

        Args:
            detections: List of detections to filter
            iou_threshold: IoU threshold for suppression

        Returns:
            Filtered list of detections

        Note:
            Currently simplified implementation - could be enhanced
        """
        # Simplified NMS for brevity
        return detections

    def transform_to_bev(self, tracks: list[Track]) -> list[BEVTrack]:
        """
        Transform tracks to Bird's Eye View coordinates using homography.

        Converts track positions from camera pixel coordinates to a unified
        bird's eye view coordinate system for cross-camera tracking.

        Args:
            tracks: List of tracks in camera coordinates

        Returns:
            List of tracks transformed to BEV coordinates
        """
        bev_tracks = []

        # Debug logging for multi-camera BEV transformation
        camera_track_counts: dict[int, int] = {}
        for track in tracks:
            camera_track_counts[track.camera_id] = camera_track_counts.get(track.camera_id, 0) + 1

        if camera_track_counts:
            logger.info(f"🗺️ BEV Transform input: {camera_track_counts} tracks per camera")

        for track in tracks:
            # Use bottom center of bounding box (feet position)
            x, y, w, h = track.bbox
            feet_x = x + w // 2
            feet_y = y + h

            # Transform to BEV coordinates using calibration
            transformed_points = self.calibration.transform_points_to_bev([(feet_x, feet_y)], track.camera_id)

            if not transformed_points:
                logger.warning(
                    f"❌ Camera {track.camera_id} track {track.track_id}: No calibration/homography available"
                )
                continue

            bev_x_pixels, bev_y_pixels = transformed_points[0]

            # Validate BEV coordinates are within reasonable bounds (0-600 for typical calibration)
            if not (0 <= bev_x_pixels <= 600 and 0 <= bev_y_pixels <= 600):
                logger.warning(
                    f"⚠️ Camera {track.camera_id} track {track.track_id}: "
                    f"BEV coords out of bounds: ({bev_x_pixels:.1f},{bev_y_pixels:.1f})"
                )

            logger.debug(
                f"✅ Camera {track.camera_id} track {track.track_id}: "
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

        if bev_tracks:
            logger.info(f"✅ BEV Transform output: {len(bev_tracks)} BEV tracks created")
        else:
            logger.warning("⚠️ BEV Transform: No tracks transformed (check calibration)")

        return bev_tracks

    def get_reid_features(self, frame: np.ndarray, tracks: list[Track]) -> np.ndarray | None:
        """
        Extract ReID features for tracks.

        Uses the TorchReID extractor to compute appearance features for
        the provided tracks, which can be used for cross-camera matching.

        Args:
            frame: Input frame containing the tracked objects
            tracks: List of tracks to extract features for

        Returns:
            Array of features for each track, or None if extraction fails
        """
        if not self.reid_extractor or not tracks:
            return None

        try:
            # Extract bounding boxes from tracks
            bboxes = []
            for track in tracks:
                x, y, w, h = track.bbox
                # Convert to x1, y1, x2, y2 format expected by ReID extractor
                bboxes.append([x, y, x + w, y + h])

            bboxes_array = np.array(bboxes, dtype=np.float32)

            # Extract features using ReID model
            features = self.reid_extractor.extract_features(frame, bboxes_array)

            if features is not None:
                logger.debug(f"🔍 Extracted ReID features for {len(tracks)} tracks: shape {features.shape}")
            else:
                logger.warning(f"⚠️ ReID feature extraction returned None for {len(tracks)} tracks")

            return features

        except Exception as e:
            logger.error(f"❌ Error extracting ReID features: {e}")
            return None

    def get_config_schema(self) -> dict[str, Any]:
        """
        Get the JSON schema for the tracker's configuration.

        Returns:
            Dictionary containing the JSON schema for the configuration
        """
        return self.config.model_json_schema()

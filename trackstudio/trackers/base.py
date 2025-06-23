"""
Base Vision Tracker

This module defines the abstract base class for vision tracking algorithms.
A tracker handles detection, single-camera tracking, and BEV transformation for one camera stream.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

import numpy as np
from pydantic import BaseModel

from ..calibration import CameraCalibration


@dataclass
class Detection:
    """
    Single detection result from object detection.

    Represents a detected object in a single frame with its bounding box,
    confidence score, and class information.

    Attributes:
        bbox: Bounding box as (x, y, width, height) in pixels
        confidence: Detection confidence score between 0 and 1
        class_name: Human-readable class name (e.g., "person", "car")
        class_id: Numeric class identifier
    """

    bbox: tuple[int, int, int, int]  # (x, y, width, height)
    confidence: float
    class_name: str
    class_id: int


@dataclass
class Track:
    """
    Single tracking result for an object across frames.

    Represents a tracked object with temporal consistency, maintaining
    identity across multiple frames within a single camera view.

    Attributes:
        track_id: Unique identifier for this track within the camera
        bbox: Current bounding box as (x, y, width, height) in pixels
        confidence: Current confidence score between 0 and 1
        age: Number of frames this track has been active
        camera_id: ID of the camera that produced this track
    """

    track_id: str
    bbox: tuple[int, int, int, int]  # (x, y, width, height)
    confidence: float
    age: int
    camera_id: int


@dataclass
class BEVTrack:
    """
    Bird's Eye View tracking result.

    Represents a tracked object transformed to bird's eye view (top-down)
    coordinates, enabling cross-camera tracking and spatial analysis.

    Attributes:
        track_id: Unique identifier for this track within the camera
        bev_x: X coordinate in bird's eye view space
        bev_y: Y coordinate in bird's eye view space
        confidence: Track confidence score between 0 and 1
        camera_id: ID of the source camera
        global_id: Optional global ID for cross-camera tracking
        trajectory: Optional list of recent positions as (x, y, timestamp) tuples
    """

    track_id: str
    bev_x: float
    bev_y: float
    confidence: float
    camera_id: int
    global_id: int | None = None  # Global ID for cross-camera tracking
    trajectory: list[tuple[float, float, float]] | None = None  # List of (x, y, timestamp) for recent positions


@dataclass
class VisionResult:
    """
    Complete vision processing result for all camera streams.

    Contains the comprehensive output of vision processing across all active
    camera streams, including detections, tracks, and performance metrics.

    Attributes:
        frame_id: Sequential frame identifier
        timestamp: Processing timestamp in seconds
        bev_tracks: List of all tracks in bird's eye view coordinates
        processing_time_ms: Total processing time in milliseconds
        num_streams: Number of active camera streams
        active_stream_ids: List of active camera stream IDs
        all_stream_detections: Detections per camera stream
        all_stream_tracks: Tracks per camera stream
    """

    frame_id: int
    timestamp: float
    bev_tracks: list[BEVTrack]
    processing_time_ms: float
    num_streams: int
    active_stream_ids: list[int]
    all_stream_detections: dict[int, list[Detection]]
    all_stream_tracks: dict[int, list[Track]]


class BaseTrackerConfig(BaseModel):
    """
    Base configuration class for vision trackers.

    Provides the foundation for all tracker configurations, allowing
    for additional fields to be added by specific tracker implementations.
    """

    class Config:
        extra = "allow"


class VisionTracker(ABC):
    """
    Abstract base class for vision tracking algorithms.

    This class defines the interface that all vision trackers must implement.
    A vision tracker is responsible for:
    1. Detecting objects in individual frames
    2. Tracking objects across frames within a single camera
    3. Transforming tracks to bird's eye view coordinates
    4. Managing configuration and providing statistics

    Attributes:
        calibration: Camera calibration module for coordinate transformations
        config: Tracker-specific configuration
    """

    def __init__(self, config: BaseTrackerConfig, calibration_file: str | None = None) -> None:
        """
        Initialize the vision tracker.

        Args:
            config: Configuration object for the tracker
            calibration_file: Optional path to calibration data file
        """
        # Initialize calibration module with specified file or default
        if calibration_file:
            self.calibration = CameraCalibration(calibration_file)
        else:
            self.calibration = CameraCalibration()
        self.config = config

    @abstractmethod
    def detect(self, frame: np.ndarray, camera_id: int) -> list[Detection]:
        """
        Detect objects in a single frame.

        Performs object detection on the provided frame and returns a list
        of detected objects with their bounding boxes and confidence scores.

        Args:
            frame: Input image as numpy array in BGR format
            camera_id: Identifier of the camera that captured this frame

        Returns:
            List of Detection objects found in the frame

        Raises:
            RuntimeError: If the detection model is not properly initialized
        """
        pass

    @abstractmethod
    def track(
        self, detections: list[Detection], camera_id: int, timestamp: float, frame: np.ndarray | None = None
    ) -> list[Track]:
        """
        Track objects across frames.

        Associates detections with existing tracks and creates new tracks
        for new objects. Maintains temporal consistency within a single camera.

        Args:
            detections: List of detections from the current frame
            camera_id: Identifier of the source camera
            timestamp: Timestamp of the current frame in seconds
            frame: Optional original frame for feature extraction

        Returns:
            List of Track objects with updated positions and IDs

        Raises:
            ValueError: If required parameters are missing or invalid
        """
        pass

    @abstractmethod
    def transform_to_bev(self, tracks: list[Track]) -> list[BEVTrack]:
        """
        Transform tracks to Bird's Eye View coordinates.

        Converts track positions from camera coordinates to a common
        bird's eye view coordinate system for cross-camera analysis.

        Args:
            tracks: List of tracks in camera coordinates

        Returns:
            List of BEVTrack objects in bird's eye view coordinates

        Raises:
            RuntimeError: If camera calibration is not available
        """
        pass

    @abstractmethod
    def get_config_schema(self) -> dict[str, Any]:
        """
        Return the JSON schema for the tracker's configuration.

        Provides a schema that describes the configuration parameters
        that this tracker accepts, used for validation and UI generation.

        Returns:
            Dictionary containing the JSON schema
        """
        pass

    @abstractmethod
    def update_config(self, config_update: dict[str, Any]) -> None:
        """
        Update the tracker's configuration.

        Applies configuration changes to the tracker, potentially affecting
        detection parameters, tracking behavior, or other settings.

        Args:
            config_update: Dictionary of configuration parameters to update

        Raises:
            ValueError: If invalid configuration parameters are provided
        """
        pass

    @abstractmethod
    def get_statistics(self) -> dict[str, Any]:
        """
        Return a dictionary of tracker-specific statistics.

        Provides runtime statistics and performance metrics for monitoring
        and debugging the tracker's behavior.

        Returns:
            Dictionary containing statistics and metrics
        """
        pass

    def get_reid_features(self, frame: np.ndarray, tracks: list[Track]) -> np.ndarray | None:
        """
        Extract ReID (Re-Identification) features for tracks.

        This is an optional method that can be implemented to extract
        appearance features for person re-identification across cameras.

        Args:
            frame: Input frame containing the tracked objects
            tracks: List of tracks to extract features for

        Returns:
            Array of features for each track, or None if not supported

        Raises:
            RuntimeError: If the ReID model fails to extract features
        """
        return None

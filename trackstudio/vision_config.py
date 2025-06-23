"""
Vision System Configuration

This module defines configuration classes for the vision tracking system,
including tracker and merger configurations with proper type annotations.
"""

from typing import Any, Literal

from pydantic import BaseModel, Field, validator

from trackstudio.config_registry import register_merger_config, register_tracker_config
from trackstudio.trackers.base import BaseTrackerConfig


def slider_field(default: float, min_val: float, max_val: float, step: float, title: str, description: str) -> float:
    """
    Factory for creating a float slider field for the UI.

    Args:
        default: Default value for the field
        min_val: Minimum allowed value
        max_val: Maximum allowed value
        step: Step size for the slider
        title: Display title for the UI
        description: Description text for the UI

    Returns:
        Field configuration for a float slider
    """
    return Field(
        default=default,
        title=title,
        description=description,
        json_schema_extra={"ui_control": "slider", "min": min_val, "max": max_val, "step": step, "type": "float"},
    )


def int_slider_field(default: int, min_val: int, max_val: int, step: int, title: str, description: str) -> int:
    """
    Factory for creating an integer slider field for the UI.

    Args:
        default: Default value for the field
        min_val: Minimum allowed value
        max_val: Maximum allowed value
        step: Step size for the slider
        title: Display title for the UI
        description: Description text for the UI

    Returns:
        Field configuration for an integer slider
    """
    return Field(
        default=default,
        title=title,
        description=description,
        json_schema_extra={"ui_control": "slider", "min": min_val, "max": max_val, "step": step, "type": "integer"},
    )


class DetectionConfig(BaseModel):
    """
    Configuration for object detection parameters.

    Attributes:
        confidence_threshold: Minimum confidence score for accepting detections
        nms_iou_threshold: IoU threshold for Non-Maximum Suppression
        min_box_width: Minimum width of valid bounding boxes
        min_box_height: Minimum height of valid bounding boxes
        max_aspect_ratio: Maximum aspect ratio (width/height) for valid boxes
    """

    confidence_threshold: float = slider_field(
        0.25, 0.1, 0.95, 0.05, "Confidence Threshold", "Minimum confidence for a detection."
    )
    nms_iou_threshold: float = slider_field(
        0.5, 0.1, 1.0, 0.05, "NMS IoU Threshold", "IoU threshold for Non-Maximum Suppression."
    )
    min_box_width: int = int_slider_field(15, 1, 200, 1, "Min Box Width", "Minimum width of a bounding box.")
    min_box_height: int = int_slider_field(30, 1, 400, 1, "Min Box Height", "Minimum height of a bounding box.")
    max_aspect_ratio: float = slider_field(4.0, 1.0, 10.0, 0.1, "Max Aspect Ratio", "Maximum aspect ratio (w/h).")


class SingleCameraTrackerConfig(BaseModel):
    """
    Configuration for single-camera tracking parameters.

    Attributes:
        tracker_max_age: Number of frames to keep a track without detection
        tracker_min_hits: Consecutive hits required to start a track
        tracker_max_iou_distance: Maximum IoU distance for track association
        tracker_max_cosine_distance: Maximum cosine distance for appearance
        tracker_matching_threshold: ReID feature matching threshold
    """

    tracker_max_age: int = int_slider_field(30, 5, 200, 1, "Max Track Age", "Frames to keep a track without detection.")
    tracker_min_hits: int = int_slider_field(1, 1, 10, 1, "Min Hits to Start", "Consecutive hits to start a track.")
    tracker_max_iou_distance: float = slider_field(
        0.7, 0.1, 1.0, 0.05, "Max IoU Distance", "Max IoU distance for track association."
    )
    tracker_max_cosine_distance: float = slider_field(
        0.3, 0.1, 1.0, 0.05, "Max Cosine Distance", "Max cosine distance for appearance."
    )
    tracker_matching_threshold: float = slider_field(
        0.3, 0.1, 1.0, 0.05, "ReID Matching Threshold", "ReID feature matching threshold."
    )


@register_tracker_config("rfdetr")
class RFDETRTrackerConfig(BaseTrackerConfig):
    """
    Configuration for RF-DETR tracker with DeepSORT and ReID.

    Combines object detection using RF-DETR with DeepSORT tracking
    and ReID-based appearance features.
    """

    detection: DetectionConfig = Field(default_factory=DetectionConfig, title="Detection Parameters")
    tracking: SingleCameraTrackerConfig = Field(
        default_factory=SingleCameraTrackerConfig, title="Single-Camera Tracking"
    )


@register_tracker_config("dummy")
class DummyTrackerConfig(BaseTrackerConfig):
    """
    Configuration for the dummy tracker.

    This is a simple tracker used for testing and development
    that doesn't require any configurable parameters.
    """

    pass


@register_merger_config("bev_cluster")
class CrossCameraConfig(BaseModel):
    """
    Configuration for BEV cluster merger.

    This merger combines tracks from multiple cameras using
    bird's eye view clustering and appearance matching.

    Attributes:
        spatial_threshold: Maximum distance in BEV pixels for track merging
        appearance_threshold: Maximum feature distance for appearance matching
        max_track_age_s: Maximum time to keep a global track without updates
        appearance_weight: Weight of appearance vs spatial distance in matching
        smoothing_alpha: Alpha for exponential smoothing of position
        velocity_alpha: Alpha for smoothing velocity estimation
    """

    spatial_threshold: float = slider_field(
        50.0,
        10.0,
        200.0,
        5.0,
        "Spatial Threshold (px)",
        "Max distance in BEV pixels to consider two tracks for merging.",
    )
    appearance_threshold: float = slider_field(
        0.4, 0.1, 1.0, 0.05, "Appearance Threshold", "Max feature distance for appearance matching. Lower is stricter."
    )
    max_track_age_s: float = slider_field(
        3.0, 1.0, 10.0, 0.5, "Max Track Age (s)", "Seconds to keep a global track without updates."
    )
    appearance_weight: float = slider_field(
        0.3, 0.0, 1.0, 0.05, "Appearance Weight", "Weight of appearance vs. spatial distance in matching (0-1)."
    )
    smoothing_alpha: float = slider_field(
        0.3, 0.0, 1.0, 0.05, "Position Smoothing", "Alpha for exponential smoothing of position. Lower is more smooth."
    )
    velocity_alpha: float = slider_field(
        0.5, 0.0, 1.0, 0.05, "Velocity Smoothing", "Alpha for smoothing velocity. Lower is more smooth."
    )


# Create the dynamic configuration system
def _create_config_system() -> tuple[type[BaseModel], str, str]:
    """
    Create the dynamic config system with auto-registration.

    This function creates a dynamic VisionSystemConfig class that includes
    all registered tracker and merger types in its schema.

    Returns:
        Tuple of (VisionSystemConfig class, TrackerType, MergerType)
    """
    from trackstudio.config_registry import get_config_classes  # noqa: PLC0415

    try:
        VisionSystemConfig, TrackerType, MergerType = get_config_classes()  # noqa: N806
        return VisionSystemConfig, TrackerType, MergerType
    except Exception as e:
        # If dynamic config creation fails, fall back to basic config
        import logging  # noqa: PLC0415

        logger = logging.getLogger(__name__)
        logger.warning(f"⚠️ Failed to get dynamic config classes, using fallback: {e}")

        # Use simplified fallback config - create a basic class
        from pydantic import BaseModel  # noqa: PLC0415

        class BasicVisionSystemConfig(BaseModel):
            """Fallback config when dynamic system is not available"""

            tracker_type: str = "dummy"  # Safe default tracker
            merger_type: str = "bev_cluster"  # Safe default merger

            def get_tracker_config(self) -> BaseTrackerConfig:
                # Try to get from registry first
                from trackstudio.config_registry import get_registered_tracker_configs  # noqa: PLC0415

                configs = get_registered_tracker_configs()
                if self.tracker_type in configs:
                    return configs[self.tracker_type]()

                # Fall back to base config if not found
                logger.warning(f"⚠️ Tracker config not found for {self.tracker_type}, using base config")
                return BaseTrackerConfig()

            def get_merger_config(self) -> BaseModel:
                # Try to get from registry first
                from trackstudio.config_registry import get_registered_merger_configs  # noqa: PLC0415

                configs = get_registered_merger_configs()
                if self.merger_type in configs:
                    return configs[self.merger_type]()

                # Fall back to empty config
                logger.warning(f"⚠️ Merger config not found for {self.merger_type}, using empty config")
                return BaseModel()

            def get_available_trackers(self) -> list[str]:
                from trackstudio.config_registry import get_tracker_names  # noqa: PLC0415

                registered = get_tracker_names()
                return registered if registered else ["dummy"]

            def get_available_mergers(self) -> list[str]:
                from trackstudio.config_registry import get_merger_names  # noqa: PLC0415

                registered = get_merger_names()
                return registered if registered else ["bev_cluster"]

        return BasicVisionSystemConfig, str, str


# Dynamic configuration system - will be created when needed
_VisionSystemConfig: type[BaseModel] | None = None
_TrackerType: str | None = None
_MergerType: str | None = None


def get_vision_system_config(force_refresh: bool = False) -> type[BaseModel]:
    """
    Get or create the dynamic VisionSystemConfig class.

    Args:
        force_refresh: Whether to force recreation of the config class

    Returns:
        The dynamic VisionSystemConfig class
    """
    global _VisionSystemConfig, _TrackerType, _MergerType  # noqa: PLW0603

    if _VisionSystemConfig is None or force_refresh:
        try:
            _VisionSystemConfig, _TrackerType, _MergerType = _create_config_system()
        except Exception as e:
            # Fallback to basic types if dynamic creation fails
            import logging  # noqa: PLC0415

            logger = logging.getLogger(__name__)
            logger.warning(f"⚠️ Could not create dynamic config system: {e}, using fallback")

            # Fallback static config that accepts any tracker type
            class _VisionSystemConfigFallback(BaseModel):
                """Fallback static configuration for the vision system"""

                tracker_type: str = Field(default="rfdetr", title="Tracker Type")
                merger_type: str = Field(default="bev_cluster", title="Merger Type")

                @validator("tracker_type")
                def validate_tracker_type(self, v: str) -> str:
                    # Accept any tracker type - validation will happen in the factory
                    return v

                @validator("merger_type")
                def validate_merger_type(self, v: str) -> str:
                    # Accept any merger type - validation will happen in the factory
                    return v

                def get_tracker_config(self) -> BaseTrackerConfig:
                    # Try to get from registry first
                    from trackstudio.config_registry import get_registered_tracker_configs  # noqa: PLC0415

                    configs = get_registered_tracker_configs()
                    if self.tracker_type in configs:
                        return configs[self.tracker_type]()

                    # Fallback to hardcoded configs
                    if self.tracker_type == "rfdetr":
                        return RFDETRTrackerConfig()
                    if self.tracker_type == "dummy":
                        return DummyTrackerConfig()
                    raise ValueError(f"Unknown tracker type: {self.tracker_type}")

                def get_merger_config(self) -> BaseModel:
                    # Try to get from registry first
                    from trackstudio.config_registry import get_registered_merger_configs  # noqa: PLC0415

                    configs = get_registered_merger_configs()
                    if self.merger_type in configs:
                        return configs[self.merger_type]()

                    # Fallback to hardcoded configs
                    if self.merger_type == "bev_cluster":
                        return CrossCameraConfig()
                    raise ValueError(f"Unknown merger type: {self.merger_type}")

                def get_available_trackers(self) -> list[str]:
                    from trackstudio.config_registry import get_tracker_names  # noqa: PLC0415

                    registered = get_tracker_names()
                    fallback = ["rfdetr", "dummy"]
                    return list(set(registered + fallback))

                def get_available_mergers(self) -> list[str]:
                    from trackstudio.config_registry import get_merger_names  # noqa: PLC0415

                    registered = get_merger_names()
                    fallback = ["bev_cluster"]
                    return list(set(registered + fallback))

            _VisionSystemConfig = _VisionSystemConfigFallback

    return _VisionSystemConfig


def refresh_config_system() -> None:
    """Force refresh of the config system to pick up newly registered trackers"""
    global _VisionSystemConfig, _TrackerType, _MergerType  # noqa: PLW0603
    _VisionSystemConfig = None
    _TrackerType = None
    _MergerType = None


# Create a proxy that calls get_vision_system_config when needed
class VisionSystemConfigMeta(type):
    """
    Metaclass for VisionSystemConfig that provides dynamic behavior.

    This metaclass allows the VisionSystemConfig class to behave dynamically
    based on registered tracker and merger types, which is essential for the UI.
    """

    def __call__(cls, *args: Any, **kwargs: Any) -> Any:
        """
        Create an instance of the dynamic config class.

        Args:
            *args: Positional arguments for the config
            **kwargs: Keyword arguments for the config

        Returns:
            Instance of the dynamic VisionSystemConfig
        """
        # Only refresh if needed, not on every call
        config_class = get_vision_system_config(force_refresh=False)
        return config_class(*args, **kwargs)

    def model_json_schema(cls) -> dict[str, Any]:
        """
        Get the JSON schema for the dynamic config class.

        Returns:
            JSON schema dictionary for the UI
        """
        config_class = get_vision_system_config(force_refresh=False)
        return config_class.model_json_schema()

    def model_dump_json(cls, *args: Any, **kwargs: Any) -> str:
        """
        Dump the model to JSON.

        Args:
            *args: Positional arguments
            **kwargs: Keyword arguments

        Returns:
            JSON string representation
        """
        config_class = get_vision_system_config(force_refresh=False)
        return config_class.model_dump_json(*args, **kwargs)


class VisionSystemConfig(metaclass=VisionSystemConfigMeta):
    """
    Dynamic Vision System Configuration - delegates to the actual implementation.

    This class uses a metaclass to provide dynamic behavior based on registered
    tracker and merger types. The UI depends on this dynamic behavior to show
    the correct configuration options.
    """

    pass


# Convenience function to get tracker type for typing
def get_tracker_type() -> str:
    """
    Get the current TrackerType for type hints.

    Returns:
        The current tracker type string
    """
    if _TrackerType is None:
        get_vision_system_config()  # This will initialize _TrackerType
    return _TrackerType or "str"


# Unused functions - removed for optimization

# Initial fallback types (will be updated when trackers are registered)
TrackerType = Literal["rfdetr", "dummy"]
MergerType = Literal["bev_cluster"]

"""
Vision System Factory

This module provides factory functions for creating complete vision systems
with tracker and merger components. It handles the initialization and configuration
of the entire vision processing pipeline.
"""

import logging

from trackstudio.merger_factory import create_merger, get_available_mergers, get_merger_type_from_env
from trackstudio.mergers.base import VisionMerger
from trackstudio.tracker_factory import create_tracker, get_available_trackers, get_tracker_type_from_env
from trackstudio.trackers.base import VisionTracker
from trackstudio.vision_config import VisionSystemConfig

logger = logging.getLogger(__name__)


def create_vision_system(
    tracker_type: str | None = None, merger_type: str | None = None, calibration_file: str | None = None
) -> tuple[VisionTracker, VisionMerger, VisionSystemConfig]:
    """
    Create a complete vision system with tracker and merger components.

    This function serves as the main entry point for creating a fully configured
    vision processing system. It handles component selection, validation,
    configuration creation, and optimization of shared resources.

    Args:
        tracker_type: Optional tracker type override (e.g., "rfdetr", "dummy").
                     If None, will be determined from environment variables.
        merger_type: Optional merger type override (e.g., "bev_cluster").
                    If None, will be determined from environment variables.
        calibration_file: Optional path to calibration data file.

    Returns:
        Tuple containing:
        - VisionTracker: Initialized tracker instance
        - VisionMerger: Initialized merger instance
        - VisionSystemConfig: System configuration object

    Raises:
        RuntimeError: If system creation fails due to invalid configuration
        ValueError: If specified tracker or merger types are not available

    Example:
        >>> tracker, merger, config = create_vision_system("rfdetr", "bev_cluster")
        >>> # Use tracker and merger for vision processing
    """
    # Determine tracker type with fallback logic
    if tracker_type is None:
        tracker_type = get_tracker_type_from_env()

    # Validate tracker type against available implementations
    available_trackers = get_available_trackers()
    if tracker_type not in available_trackers:
        logger.warning(f"⚠️ Unknown tracker type: {tracker_type}, available: {available_trackers}")
        if available_trackers:
            tracker_type = available_trackers[0]
            logger.info(f"🔄 Falling back to tracker: {tracker_type}")
        else:
            tracker_type = "dummy"
            logger.warning("🔄 No trackers available, using dummy tracker")

    # Determine merger type with fallback logic
    if merger_type is None:
        merger_type = get_merger_type_from_env()

    # Validate merger type against available implementations
    available_mergers = get_available_mergers()
    if merger_type not in available_mergers:
        logger.warning(f"⚠️ Unknown merger type: {merger_type}, available: {available_mergers}")
        if available_mergers:
            merger_type = available_mergers[0]
            logger.info(f"🔄 Falling back to merger: {merger_type}")
        else:
            merger_type = "bev_cluster"
            logger.warning("🔄 No mergers available, using default bev_cluster")

    # Create configuration with validated component types
    try:
        config = VisionSystemConfig(tracker_type=tracker_type, merger_type=merger_type)  # type: ignore
        logger.debug(f"✅ Created vision system config: {tracker_type} + {merger_type}")
    except Exception as e:
        logger.error(f"❌ Failed to create config with tracker_type={tracker_type}, merger_type={merger_type}: {e}")
        # Fallback to default configuration
        config = VisionSystemConfig()  # type: ignore
        # Apply the selected types to the default config if possible
        if hasattr(config, "tracker_type"):
            config.tracker_type = tracker_type  # type: ignore
        if hasattr(config, "merger_type"):
            config.merger_type = merger_type  # type: ignore
        logger.info("🔄 Using fallback configuration")

    # Create tracker and merger instances
    try:
        tracker = create_tracker(config, calibration_file)
        merger = create_merger(config)
        logger.debug(f"✅ Created tracker: {type(tracker).__name__}")
        logger.debug(f"✅ Created merger: {type(merger).__name__}")
    except Exception as e:
        logger.error(f"❌ Failed to create vision components: {e}")
        raise RuntimeError(f"Failed to initialize vision system: {e}") from e

    # Optimization: Share ReID extractor between components to reduce memory usage
    _optimize_shared_resources(tracker, merger)

    logger.info(f"🧠 Vision system created successfully with {tracker_type} tracker and {merger_type} merger")

    return tracker, merger, config


def _optimize_shared_resources(tracker: VisionTracker, merger: VisionMerger) -> None:
    """
    Optimize shared resources between tracker and merger components.

    This internal function identifies opportunities to share expensive resources
    like ReID feature extractors between the tracker and merger to reduce
    memory usage and improve performance.

    Args:
        tracker: The initialized tracker instance
        merger: The initialized merger instance

    Note:
        This function modifies the components in-place to share resources.
    """
    # Check if both components have ReID extractors that can be shared
    if hasattr(tracker, "reid_extractor") and hasattr(merger, "reid_extractor"):
        tracker_has_reid = getattr(tracker, "reid_extractor", None) is not None
        merger_has_reid = getattr(merger, "reid_extractor", None) is not None

        if tracker_has_reid and not merger_has_reid:
            # Share tracker's ReID extractor with merger
            merger.reid_extractor = tracker.reid_extractor
            logger.info("♻️ Shared ReID extractor from tracker to merger")
        elif merger_has_reid and not tracker_has_reid:
            # Share merger's ReID extractor with tracker
            tracker.reid_extractor = merger.reid_extractor
            logger.info("♻️ Shared ReID extractor from merger to tracker")
        elif tracker_has_reid and merger_has_reid:
            logger.debug("ℹ️ Both components have ReID extractors - no sharing needed")


def get_available_vision_systems() -> list[tuple[str, str]]:
    """
    Get all available combinations of tracker and merger types.

    Returns a list of all valid (tracker_type, merger_type) combinations
    that can be used to create vision systems.

    Returns:
        List of tuples where each tuple contains (tracker_type, merger_type)

    Example:
        >>> combinations = get_available_vision_systems()
        >>> print(combinations)
        [('rfdetr', 'bev_cluster'), ('dummy', 'bev_cluster'), ...]
    """
    trackers = get_available_trackers()
    mergers = get_available_mergers()

    combinations = []
    combinations.extend((tracker_type, merger_type) for tracker_type in trackers for merger_type in mergers)

    logger.debug(f"📋 Available vision system combinations: {len(combinations)}")
    return combinations


def validate_vision_system_config(tracker_type: str, merger_type: str) -> bool:
    """
    Validate that a specific tracker and merger combination is supported.

    Checks if the specified tracker and merger types are available and
    compatible with each other.

    Args:
        tracker_type: The tracker type to validate
        merger_type: The merger type to validate

    Returns:
        True if the combination is valid and supported, False otherwise

    Example:
        >>> is_valid = validate_vision_system_config("rfdetr", "bev_cluster")
        >>> if is_valid:
        ...     tracker, merger, config = create_vision_system("rfdetr", "bev_cluster")
    """
    available_trackers = get_available_trackers()
    available_mergers = get_available_mergers()

    tracker_valid = tracker_type in available_trackers
    merger_valid = merger_type in available_mergers

    if not tracker_valid:
        logger.warning(f"❌ Invalid tracker type: {tracker_type}")
    if not merger_valid:
        logger.warning(f"❌ Invalid merger type: {merger_type}")

    is_valid = tracker_valid and merger_valid
    logger.debug(f"✅ Vision system config validation: {is_valid}")

    return is_valid

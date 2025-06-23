"""
Vision Tracker Factory

This module provides factory functions for creating vision trackers
based on configuration, enabling easy extensibility for new algorithms.
It handles dynamic loading, registration, and initialization of tracker components.
"""

import logging
import os
from collections.abc import Callable
from typing import Any

from trackstudio.config_registry import get_registered_tracker_configs, get_tracker_names
from trackstudio.trackers.base import VisionTracker
from trackstudio.trackers.dummy import DummyVisionTracker
from trackstudio.vision_config import VisionSystemConfig

logger = logging.getLogger(__name__)


def create_tracker(config: VisionSystemConfig, calibration_file: str | None = None) -> VisionTracker:
    """
    Create a vision tracker based on the configuration.

    This function serves as the main factory method for creating tracker instances.
    It supports both built-in trackers and dynamically registered custom trackers,
    with automatic dependency handling and fallback mechanisms.

    Args:
        config: Vision system configuration containing tracker type and parameters
        calibration_file: Optional path to calibration data file

    Returns:
        Configured and initialized vision tracker instance

    Raises:
        ImportError: If required dependencies for the tracker are not available
        ValueError: If the specified tracker type is not supported
        RuntimeError: If tracker initialization fails

    Example:
        >>> from trackstudio.vision_config import VisionSystemConfig
        >>> config = VisionSystemConfig(tracker_type="rfdetr")
        >>> tracker = create_tracker(config)
        >>> detections = tracker.detect(frame, camera_id=0)
    """
    tracker_type = config.tracker_type
    tracker_config = config.get_tracker_config()

    # Get registered tracker configs for dynamic lookup
    registered_configs = get_registered_tracker_configs()

    logger.info(f"🏭 Creating tracker of type: {tracker_type}")

    if tracker_type == "dummy":
        logger.info("🤖 Creating DummyVisionTracker for testing/development")
        return DummyVisionTracker(config=tracker_config, calibration_file=calibration_file)

    if tracker_type == "rfdetr":
        logger.info("🎯 Creating RFDETRTracker with object detection")
        try:
            # Import here to avoid importing when not needed
            from trackstudio.trackers.rfdetr import RFDETRTracker  # noqa: PLC0415

            return RFDETRTracker(config=tracker_config, calibration_file=calibration_file)
        except ImportError as e:
            logger.error(f"❌ Failed to import RFDETRTracker: {e}")
            logger.error("Required dependencies missing. Install with: pip install rfdetr supervision")
            raise ImportError(f"RFDETRTracker dependencies not available: {e}") from e

    # Check if it's a directly registered tracker class first
    elif tracker_type in TRACKER_REGISTRY:
        logger.info(f"🔧 Creating registered tracker class: {tracker_type}")
        tracker_class = TRACKER_REGISTRY[tracker_type]
        try:
            return tracker_class(config=tracker_config, calibration_file=calibration_file)
        except Exception as e:
            logger.error(f"❌ Failed to initialize {tracker_type} tracker: {e}")
            raise RuntimeError(f"Tracker initialization failed: {e}") from e

    # Check if it's a dynamically registered tracker config
    elif tracker_type in registered_configs:
        logger.info(f"🔧 Creating dynamically registered tracker: {tracker_type}")
        return _create_dynamic_tracker(tracker_type, tracker_config)
    else:
        available_trackers = get_tracker_names()
        error_msg = f"Unsupported tracker type: {tracker_type}. Available trackers: {available_trackers}"
        logger.error(f"❌ {error_msg}")
        raise ValueError(error_msg)


def _create_dynamic_tracker(tracker_type: str, tracker_config: Any) -> VisionTracker:
    """
    Create a dynamically registered tracker.

    This internal function handles the creation of trackers that are registered
    at runtime through the configuration system.

    Args:
        tracker_type: Name of the tracker type to create
        tracker_config: Configuration object for the tracker

    Returns:
        Initialized tracker instance

    Raises:
        ImportError: If the tracker module cannot be imported
        AttributeError: If the tracker class is not found in the module
    """
    try:
        # Try to import from trackers module
        module_name = f"vision.trackers.{tracker_type}_tracker"
        tracker_class_name = f"{tracker_type.title()}Tracker"

        logger.debug(f"Attempting to import {tracker_class_name} from {module_name}")
        module = __import__(module_name, fromlist=[tracker_class_name])
        tracker_class = getattr(module, tracker_class_name)

        return tracker_class(config=tracker_config)
    except (ImportError, AttributeError) as e:
        logger.error(f"❌ Failed to import {tracker_type} tracker: {e}")
        raise ImportError(f"{tracker_type} tracker not available: {e}") from e


def get_tracker_type_from_env() -> str:
    """
    Get tracker type from environment variable with fallback logic.

    Checks the VISION_TRACKER_TYPE environment variable and validates it
    against available trackers, providing sensible fallbacks if needed.

    Returns:
        Validated tracker type string

    Environment Variables:
        VISION_TRACKER_TYPE: Preferred tracker type (default: "rfdetr")

    Example:
        >>> # Set environment variable
        >>> os.environ["VISION_TRACKER_TYPE"] = "dummy"
        >>> tracker_type = get_tracker_type_from_env()
        >>> print(tracker_type)  # "dummy"
    """
    env_tracker = os.getenv("VISION_TRACKER_TYPE", "rfdetr").lower()

    # Validate against registered trackers
    available_trackers = get_tracker_names()

    if env_tracker in available_trackers:
        logger.debug(f"✅ Using tracker from environment: {env_tracker}")
        return env_tracker
    logger.warning(f"⚠️ Unknown tracker type in environment: {env_tracker}, available: {available_trackers}")
    # Prefer rfdetr as default, but allow other registered trackers
    if "rfdetr" in available_trackers:
        logger.info("🔄 Falling back to default tracker: rfdetr")
        return "rfdetr"
    if available_trackers:
        fallback = available_trackers[0]
        logger.info(f"🔄 Falling back to first available tracker: {fallback}")
        return fallback
    logger.warning("🔄 No trackers available, using dummy tracker")
    return "dummy"


# Registry for tracker classes (for custom trackers defined outside the module)
TRACKER_REGISTRY: dict[str, type[VisionTracker]] = {
    "dummy": DummyVisionTracker,
    # "rfdetr" is imported dynamically to avoid dependency issues
}


def register_tracker(name: str, tracker_class: type[VisionTracker]) -> None:
    """
    Register a new tracker type for runtime extensibility.

    This function allows external modules to register custom tracker implementations
    that can be used throughout the system without modifying core code.

    Args:
        name: Unique name for the tracker (will be used as tracker_type)
        tracker_class: Class that implements the VisionTracker interface

    Raises:
        ValueError: If the tracker name is already registered
        TypeError: If the tracker class doesn't inherit from VisionTracker

    Example:
        >>> class MyCustomTracker(VisionTracker):
        ...     def detect(self, frame, camera_id):
        ...         # Custom implementation
        ...         return []
        >>>
        >>> register_tracker("mycustom", MyCustomTracker)
        >>> # Now "mycustom" can be used as a tracker_type
    """
    if not issubclass(tracker_class, VisionTracker):
        raise TypeError(f"Tracker class {tracker_class.__name__} must inherit from VisionTracker")

    if name in TRACKER_REGISTRY:
        logger.warning(f"⚠️ Overriding existing tracker registration: {name}")

    TRACKER_REGISTRY[name] = tracker_class
    logger.info(f"✅ Registered tracker: {name} -> {tracker_class.__name__}")


def register_tracker_class(name: str) -> Callable[[type[VisionTracker]], type[VisionTracker]]:
    """
    Decorator to register a tracker class directly.

    This provides a convenient decorator-based API for registering tracker classes
    at definition time.

    Args:
        name: Unique name for the tracker

    Returns:
        Decorator function that registers the class

    Raises:
        ValueError: If the tracker name is invalid
        TypeError: If the decorated class doesn't inherit from VisionTracker

    Example:
        >>> @register_tracker_class("awesome")
        ... class AwesomeTracker(VisionTracker):
        ...     def detect(self, frame, camera_id):
        ...         return []
        >>>
        >>> # AwesomeTracker is now registered as "awesome"
    """

    def decorator(tracker_class: type[VisionTracker]) -> type[VisionTracker]:
        register_tracker(name, tracker_class)
        return tracker_class

    return decorator


def get_available_trackers() -> list[str]:
    """
    Get list of all available tracker types.

    Returns all tracker types that can be used to create tracker instances,
    including both built-in and registered custom trackers.

    Returns:
        List of available tracker type strings

    Example:
        >>> trackers = get_available_trackers()
        >>> print(trackers)
        ['dummy', 'rfdetr', 'mycustom']
    """
    # Combine registered trackers with dynamically discovered ones
    registry_trackers = list(TRACKER_REGISTRY.keys())
    config_trackers = get_tracker_names()

    # Merge and deduplicate
    all_trackers = list(set(registry_trackers + config_trackers))
    all_trackers.sort()  # Sort for consistent ordering

    logger.debug(f"📋 Available trackers: {all_trackers}")
    return all_trackers


def unregister_tracker(name: str) -> bool:
    """
    Unregister a previously registered tracker.

    Removes a tracker from the registry, making it unavailable for creation.
    This is primarily useful for testing or dynamic reconfiguration.

    Args:
        name: Name of the tracker to unregister

    Returns:
        True if the tracker was successfully unregistered, False if not found

    Example:
        >>> register_tracker("test", MyTestTracker)
        >>> unregister_tracker("test")
        True
        >>> unregister_tracker("nonexistent")
        False
    """
    if name in TRACKER_REGISTRY:
        del TRACKER_REGISTRY[name]
        logger.info(f"🗑️ Unregistered tracker: {name}")
        return True
    logger.warning(f"⚠️ Attempted to unregister unknown tracker: {name}")
    return False


def get_tracker_info(tracker_type: str) -> dict[str, Any]:
    """
    Get information about a specific tracker type.

    Provides metadata and configuration information about a tracker,
    useful for debugging and introspection.

    Args:
        tracker_type: Name of the tracker to get information about

    Returns:
        Dictionary containing tracker information

    Raises:
        ValueError: If the tracker type is not available

    Example:
        >>> info = get_tracker_info("rfdetr")
        >>> print(info["class_name"])
        'RFDETRTracker'
    """
    if tracker_type not in get_available_trackers():
        raise ValueError(f"Unknown tracker type: {tracker_type}")

    info = {
        "type": tracker_type,
        "available": True,
        "registered": tracker_type in TRACKER_REGISTRY,
    }

    if tracker_type in TRACKER_REGISTRY:
        tracker_class = TRACKER_REGISTRY[tracker_type]
        info.update(
            {
                "class_name": tracker_class.__name__,
                "module": tracker_class.__module__,
                "docstring": tracker_class.__doc__,
            }
        )

    return info

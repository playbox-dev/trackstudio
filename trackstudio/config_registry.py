"""
Configuration Registry System

This module provides automatic registration and discovery of tracker configurations,
making it much easier to add new trackers without modifying multiple files.
"""

import logging
from collections.abc import Callable
from typing import cast

from pydantic import BaseModel, Field, create_model

from trackstudio.trackers.base import BaseTrackerConfig

logger = logging.getLogger(__name__)

# Global registry for tracker configurations
_TRACKER_CONFIGS: dict[str, type[BaseTrackerConfig]] = {}
_MERGER_CONFIGS: dict[str, type[BaseModel]] = {}


def register_tracker_config(name: str) -> Callable[[type[BaseTrackerConfig]], type[BaseTrackerConfig]]:
    """
    Decorator to automatically register a tracker configuration.

    Args:
        name: Name to register the tracker config under

    Returns:
        Decorator function that registers the tracker configuration class

    Raises:
        ValueError: If the config class doesn't inherit from BaseTrackerConfig

    Usage:
        @register_tracker_config("mytracker")
        class MyTrackerConfig(BaseTrackerConfig):
            param: float = 0.5
    """

    def decorator(config_class: type[BaseTrackerConfig]) -> type[BaseTrackerConfig]:
        """
        Inner decorator function that performs the registration.

        Args:
            config_class: The configuration class to register

        Returns:
            The same configuration class (unmodified)
        """
        if not issubclass(config_class, BaseTrackerConfig):
            raise ValueError(f"Config class {config_class.__name__} must inherit from BaseTrackerConfig")

        _TRACKER_CONFIGS[name] = config_class
        logger.debug(f"📝 Registered tracker config: {name} -> {config_class.__name__}")

        # Only refresh if the config system is already initialized
        try:
            from .vision_config import refresh_config_system  # noqa: PLC0415

            refresh_config_system()
        except ImportError:
            # config module not imported yet, that's okay
            pass

        return config_class

    return decorator


def register_merger_config(name: str) -> Callable[[type[BaseModel]], type[BaseModel]]:
    """
    Decorator to automatically register a merger configuration.

    Args:
        name: Name to register the merger config under

    Returns:
        Decorator function that registers the merger configuration class

    Raises:
        ValueError: If the config class doesn't inherit from BaseModel

    Usage:
        @register_merger_config("bev_cluster")
        class BEVClusterConfig(BaseModel):
            threshold: float = 0.5
    """

    def decorator(config_class: type[BaseModel]) -> type[BaseModel]:
        """
        Inner decorator function that performs the registration.

        Args:
            config_class: The configuration class to register

        Returns:
            The same configuration class (unmodified)
        """
        if not issubclass(config_class, BaseModel):
            raise ValueError(f"Config class {config_class.__name__} must inherit from BaseModel")

        _MERGER_CONFIGS[name] = config_class
        logger.debug(f"📝 Registered merger config: {name} -> {config_class.__name__}")

        # Only refresh if the config system is already initialized
        try:
            from .vision_config import refresh_config_system  # noqa: PLC0415

            refresh_config_system()
        except ImportError:
            # config module not imported yet, that's okay
            pass

        return config_class

    return decorator


def get_registered_tracker_configs() -> dict[str, type[BaseTrackerConfig]]:
    """
    Get all registered tracker configurations.

    Returns:
        Dictionary mapping tracker names to their configuration classes
    """
    return _TRACKER_CONFIGS.copy()


def get_registered_merger_configs() -> dict[str, type[BaseModel]]:
    """
    Get all registered merger configurations.

    Returns:
        Dictionary mapping merger names to their configuration classes
    """
    return _MERGER_CONFIGS.copy()


def get_tracker_names() -> list[str]:
    """
    Get list of all registered tracker names.

    Returns:
        List of registered tracker names
    """
    return list(_TRACKER_CONFIGS.keys())


def get_merger_names() -> list[str]:
    """
    Get list of all registered merger names.

    Returns:
        List of registered merger names
    """
    return list(_MERGER_CONFIGS.keys())


def create_vision_system_config() -> tuple[type[BaseModel], str, str]:
    """
    Dynamically create VisionSystemConfig with all registered tracker and merger configs.

    This eliminates the need to manually update the config class when adding new trackers.
    The function creates a dynamic Pydantic model with fields for each registered configuration.

    Returns:
        Tuple containing:
        - VisionSystemConfig: Dynamically created configuration class
        - TrackerType: String representing available tracker types
        - MergerType: String representing available merger types

    Raises:
        ValueError: If no tracker configurations are registered
    """
    # Get registered names
    tracker_names = get_tracker_names()
    if not tracker_names:
        raise ValueError("No tracker configurations registered")

    merger_names = get_merger_names() or ["bev_cluster"]

    # Create TrackerType and MergerType as strings for mypy compatibility
    tracker_type_union = "|".join(tracker_names)  # e.g., "rfdetr|dummy"
    merger_type_union = "|".join(merger_names)  # e.g., "bev_cluster"

    # Dynamically create fields for the model
    field_definitions = {}

    # Add tracker_type field with dynamic choices
    field_definitions["tracker_type"] = (
        str,
        Field(
            default=tracker_names[0] if tracker_names else "dummy",
            title="Tracker Type",
            description=f"Vision tracker algorithm to use. Available: {', '.join(tracker_names)}",
        ),
    )

    # Add merger_type field with dynamic choices
    field_definitions["merger_type"] = (
        str,
        Field(
            default=merger_names[0] if merger_names else "bev_cluster",
            title="Merger Type",
            description=f"Cross-camera merger algorithm to use. Available: {', '.join(merger_names)}",
        ),
    )

    # Add configuration fields for each tracker
    for tracker_name in tracker_names:
        tracker_config_class = _TRACKER_CONFIGS.get(tracker_name)
        if tracker_config_class:
            field_name = f"{tracker_name}_tracker"
            field_definitions[field_name] = (
                tracker_config_class,
                Field(default_factory=tracker_config_class, title=f"{tracker_name.title()} Tracker Config"),
            )

    # Add configuration fields for each merger
    for merger_name in merger_names:
        merger_config_class = _MERGER_CONFIGS.get(merger_name)
        if merger_config_class:
            field_name = f"{merger_name}_merger"
            field_definitions[field_name] = (
                merger_config_class,
                Field(default_factory=merger_config_class, title=f"{merger_name.title()} Merger Config"),
            )

    # Create the dynamic model using create_model
    vision_system_config = create_model("VisionSystemConfig", **field_definitions, __base__=BaseModel)

    # Rebuild the model to resolve forward references
    vision_system_config.model_rebuild()

    # Add helper methods to the class
    def get_tracker_config(self: BaseModel) -> BaseTrackerConfig:
        """
        Get the config for the currently selected tracker.

        Returns:
            Configuration object for the selected tracker

        Raises:
            ValueError: If tracker type is unknown
        """
        tracker_type = getattr(self, "tracker_type", None)
        field_name = f"{tracker_type}_tracker"
        if hasattr(self, field_name):
            return cast(BaseTrackerConfig, getattr(self, field_name))
        raise ValueError(f"Unknown tracker type: {tracker_type}")

    def get_merger_config(self: BaseModel) -> BaseModel:
        """
        Get the config for the currently selected merger.

        Returns:
            Configuration object for the selected merger

        Raises:
            ValueError: If merger type is unknown
        """
        merger_type = getattr(self, "merger_type", None)
        field_name = f"{merger_type}_merger"
        if hasattr(self, field_name):
            return cast(BaseModel, getattr(self, field_name))
        raise ValueError(f"Unknown merger type: {merger_type}")

    def get_available_trackers(_self: BaseModel) -> list[str]:
        """
        Get list of available tracker types.

        Returns:
            List of tracker type names
        """
        return get_tracker_names()

    def get_available_mergers(_self: BaseModel) -> list[str]:
        """
        Get list of available merger types.

        Returns:
            List of merger type names
        """
        return get_merger_names()

    # Add methods to the class
    vision_system_config.get_tracker_config = get_tracker_config  # type: ignore
    vision_system_config.get_merger_config = get_merger_config  # type: ignore
    vision_system_config.get_available_trackers = get_available_trackers  # type: ignore
    vision_system_config.get_available_mergers = get_available_mergers  # type: ignore

    # Add docstring
    vision_system_config.__doc__ = """
    Dynamically generated configuration for the entire vision system.

    This configuration is automatically created based on registered tracker
    and merger configurations. Adding new trackers only requires decorating
    the config class with @register_tracker_config("name").
    """

    return vision_system_config, tracker_type_union, merger_type_union


def import_all_configs() -> None:
    """
    Import all config modules to trigger registration.

    This should be called before creating the VisionSystemConfig.
    It ensures all configuration classes are registered before the
    dynamic system configuration is created.
    """
    try:
        # Import tracker configs to trigger registration
        import importlib.util  # noqa: PLC0415

        if importlib.util.find_spec("trackstudio.vision_config") is not None:
            logger.debug("📦 Vision config module available")
    except ImportError as e:
        logger.warning(f"⚠️ Could not import vision configs: {e}")

    logger.info(f"📋 Config registry loaded: {len(_TRACKER_CONFIGS)} trackers, {len(_MERGER_CONFIGS)} mergers")


def get_config_classes() -> tuple[type[BaseModel], str, str]:
    """
    Get the dynamically created config classes.

    This is the main entry point for getting the dynamic configuration system.
    It imports all configurations and creates the dynamic VisionSystemConfig.

    Returns:
        Tuple containing the VisionSystemConfig class and type information
    """
    import_all_configs()
    return create_vision_system_config()

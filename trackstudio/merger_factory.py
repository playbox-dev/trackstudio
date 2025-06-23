"""
Vision Merger Factory

This module provides factory functions for creating vision mergers
based on configuration, enabling easy extensibility for new algorithms.
"""

import logging
import os

from trackstudio.config_registry import get_merger_names, get_registered_merger_configs
from trackstudio.mergers.base import VisionMerger
from trackstudio.mergers.bev_cluster import BEVClusterMerger
from trackstudio.models.reid_extractor import TorchReIDExtractor
from trackstudio.trackers.base import VisionTracker
from trackstudio.vision_config import VisionSystemConfig

logger = logging.getLogger(__name__)


def create_merger(config: VisionSystemConfig, _tracker: VisionTracker | None = None) -> VisionMerger:
    """
    Create a vision merger based on configuration.

    Args:
        config: Vision system configuration

    Returns:
        Configured vision merger
    """
    merger_type = getattr(config, "merger_type", "bev_cluster")
    merger_config = config.get_merger_config()

    # Get registered merger configs for dynamic lookup
    registered_configs = get_registered_merger_configs()

    if merger_type == "bev_cluster":
        logger.info("🔗 Creating BEVClusterMerger")
        return _create_bev_cluster_merger(merger_config)

    # Check if it's a dynamically registered merger
    if merger_type in registered_configs:
        logger.info(f"🔧 Creating registered merger: {merger_type}")
        try:
            # Try to import from mergers module
            module_name = f"vision.mergers.{merger_type}_merger"
            merger_class_name = f"{merger_type.replace('_', '').title()}Merger"

            module = __import__(module_name, fromlist=[merger_class_name])
            merger_class = getattr(module, merger_class_name)

            # Most mergers will need ReID extractor
            reid_extractor = _create_reid_extractor()
            return merger_class(config=merger_config, reid_extractor=reid_extractor)

        except (ImportError, AttributeError) as e:
            logger.error(f"❌ Failed to import {merger_type} merger: {e}")
            logger.warning("⚠️ Falling back to BEV cluster merger")
            return _create_bev_cluster_merger(merger_config)
    else:
        available_mergers = get_merger_names()
        logger.warning(f"Unknown merger type: {merger_type}, available: {available_mergers}, using BEV cluster")
        return _create_bev_cluster_merger(merger_config)


def _create_reid_extractor() -> TorchReIDExtractor | None:
    """Create ReID extractor using singleton pattern for memory efficiency"""
    from trackstudio.models.reid_singleton import get_reid_extractor  # noqa: PLC0415

    reid_extractor = get_reid_extractor(model_name="osnet_x0_25")
    if reid_extractor is None:
        logger.warning("⚠️ Using cross-camera merger without ReID features")

    return reid_extractor


def _create_bev_cluster_merger(merger_config) -> BEVClusterMerger:
    """Create BEV cluster merger with ReID extractor"""
    reid_extractor = _create_reid_extractor()
    return BEVClusterMerger(config=merger_config, reid_extractor=reid_extractor)


def get_available_mergers() -> list[str]:
    """Get list of all available merger types"""
    return get_merger_names()


def get_merger_type_from_env() -> str:
    """
    Get merger type from environment variable.

    Returns:
        Merger type from environment or default
    """
    env_merger = os.getenv("VISION_MERGER_TYPE", "bev_cluster").lower()

    # Validate against registered mergers
    available_mergers = get_merger_names()

    if env_merger in available_mergers:
        return env_merger
    logger.warning(
        f"Unknown merger type in environment: {env_merger}, available: {available_mergers}, using default: bev_cluster"
    )
    return (
        "bev_cluster"
        if "bev_cluster" in available_mergers
        else available_mergers[0]
        if available_mergers
        else "bev_cluster"
    )

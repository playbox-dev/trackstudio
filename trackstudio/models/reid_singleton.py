"""
ReID Extractor Singleton

This module provides a singleton pattern for ReID extractors to prevent
loading multiple instances and reduce GPU memory usage.
"""

import logging

import torch

from .reid_extractor import TorchReIDExtractor

logger = logging.getLogger(__name__)


class ReIDExtractorSingleton:
    """Singleton class for managing ReID extractor instances"""

    _instance: TorchReIDExtractor | None = None
    _model_name: str | None = None
    _device: str | None = None

    @classmethod
    def get_instance(cls, model_name: str = "osnet_x0_25", device: str | None = None) -> TorchReIDExtractor | None:
        """
        Get the singleton ReID extractor instance.

        Args:
            model_name: Name of the ReID model to use
            device: Device to run on (cuda/cpu), auto-detected if None

        Returns:
            ReID extractor instance or None if creation failed
        """
        if device is None:
            device = "cuda" if torch.cuda.is_available() else "cpu"

        # Return existing instance if it matches requirements
        if cls._instance is not None and cls._model_name == model_name and cls._device == device:
            logger.debug(f"♻️ Reusing existing ReID extractor ({model_name} on {device})")
            return cls._instance

        # Create new instance if needed
        try:
            logger.info(f"🧠 Creating new ReID extractor: {model_name} on {device}")
            cls._instance = TorchReIDExtractor(model_name=model_name, device=device)
            cls._model_name = model_name
            cls._device = device
            logger.info("✅ ReID extractor singleton created successfully")
            return cls._instance
        except Exception as e:
            logger.error(f"❌ Failed to create ReID extractor: {e}")
            cls._instance = None
            cls._model_name = None
            cls._device = None
            return None

    @classmethod
    def clear_instance(cls) -> None:
        """Clear the singleton instance (useful for testing or cleanup)"""
        if cls._instance is not None:
            logger.info("🧹 Clearing ReID extractor singleton")
            cls._instance = None
            cls._model_name = None
            cls._device = None

    @classmethod
    def is_initialized(cls) -> bool:
        """Check if singleton is initialized"""
        return cls._instance is not None


def get_reid_extractor(model_name: str = "osnet_x0_25", device: str | None = None) -> TorchReIDExtractor | None:
    """
    Convenience function to get ReID extractor singleton.

    Args:
        model_name: Name of the ReID model to use
        device: Device to run on (cuda/cpu), auto-detected if None

    Returns:
        ReID extractor instance or None if creation failed
    """
    return ReIDExtractorSingleton.get_instance(model_name, device)

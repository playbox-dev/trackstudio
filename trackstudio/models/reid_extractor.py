"""
TorchReID Feature Extractor Wrapper

This module provides a wrapper for TorchReID's feature extraction functionality,
enabling deep learning-based person re-identification features.
"""

import logging

import numpy as np
import torch

logger = logging.getLogger(__name__)


class TorchReIDExtractor:
    """Wrapper for TorchReID feature extraction"""

    def __init__(
        self, model_name: str = "osnet_x0_25", device: str | None = None, image_size: tuple[int, int] = (256, 128)
    ):
        """
        Initialize TorchReID feature extractor

        Args:
            model_name: Name of the ReID model (e.g., 'osnet_x0_25', 'osnet_x1_0')
            device: Device to run on ('cuda' or 'cpu'), auto-detect if None
            image_size: Input image size for the model (height, width)
        """
        self.model_name = model_name
        self.image_size = image_size

        if device is None:
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
        else:
            self.device = device

        self.extractor = None
        self._initialize_extractor()

        # Verify extractor was properly initialized
        if self.extractor is None:
            raise RuntimeError("TorchReID extractor failed to initialize properly")

    def _initialize_extractor(self):
        """Initialize the TorchReID feature extractor"""
        try:
            # Try different import paths for torchreid
            try:
                from torchreid import FeatureExtractor  # noqa: PLC0415

                logger.info("✅ Imported FeatureExtractor from torchreid")
            except ImportError:
                try:
                    from torchreid.utils import FeatureExtractor  # noqa: PLC0415

                    logger.info("✅ Imported FeatureExtractor from torchreid.utils")
                except ImportError:
                    # Try the reid.utils path suggested in the error
                    from torchreid.reid.utils import FeatureExtractor  # noqa: PLC0415

                    logger.info("✅ Imported FeatureExtractor from torchreid.reid.utils")

            self.extractor = FeatureExtractor(
                model_name=self.model_name,
                device=self.device,
                image_size=self.image_size,
            )
            logger.info(f"✅ TorchReID extractor initialized: {self.model_name} on {self.device}")

        except ImportError as e:
            logger.error(f"❌ Failed to import torchreid: {e}")
            logger.error("Please install: pip install torchreid")
            raise ImportError(f"torchreid is required for ReID functionality: {e}") from e
        except Exception as e:
            logger.error(f"❌ Failed to initialize TorchReID extractor: {e}")
            raise RuntimeError(f"TorchReID extractor initialization failed: {e}") from e

    def extract_features(self, frame: np.ndarray, detections) -> np.ndarray | None:
        """
        Extract ReID features from detected persons

        Args:
            frame: Input frame (H, W, 3)
            detections: supervision.Detections object or bboxes as (N, 4) array with [x1, y1, x2, y2] format

        Returns:
            Feature vectors as (N, feature_dim) array, or None if extraction fails
        """
        # Handle different input types - support both supervision.Detections and numpy arrays
        bboxes = None
        try:
            # Import supervision here to avoid circular imports
            import supervision as sv  # noqa: PLC0415

            if isinstance(detections, sv.Detections):
                if hasattr(detections, "xyxy") and len(detections.xyxy) > 0:
                    bboxes = detections.xyxy
            elif isinstance(detections, np.ndarray):
                bboxes = detections
            else:
                # Try to convert to numpy array
                bboxes = np.array(detections)
        except ImportError:
            # supervision not available, assume numpy array
            bboxes = detections if isinstance(detections, np.ndarray) else np.array(detections)

        if bboxes is None or len(bboxes) == 0:
            return np.array([])
        if self.extractor is None:
            logger.error("Extractor not initialized")
            return None

        if len(bboxes) == 0:
            return np.array([])

        # Convert to numpy array and validate bounds
        bboxes = np.array(bboxes)
        h, w = frame.shape[:2]
        bboxes[:, 0] = np.clip(bboxes[:, 0], 0, w - 1)
        bboxes[:, 1] = np.clip(bboxes[:, 1], 0, h - 1)
        bboxes[:, 2] = np.clip(bboxes[:, 2], bboxes[:, 0] + 1, w)
        bboxes[:, 3] = np.clip(bboxes[:, 3], bboxes[:, 1] + 1, h)

        try:
            # Ensure bboxes are integers
            bboxes = bboxes.astype(int)

            # Extract person crops
            crops = []
            h, w = frame.shape[:2]

            for bbox in bboxes:
                x1, y1, x2, y2 = bbox

                # Ensure bbox is within frame bounds
                x1 = max(0, min(x1, w - 1))
                y1 = max(0, min(y1, h - 1))
                x2 = max(x1 + 1, min(x2, w))
                y2 = max(y1 + 1, min(y2, h))

                # Skip too small boxes
                if (x2 - x1) < 10 or (y2 - y1) < 10:
                    # Add zero feature for invalid boxes
                    crops.append(np.zeros((10, 10, 3), dtype=np.uint8))
                    continue

                crop = frame[y1:y2, x1:x2]
                crops.append(crop)

            if len(crops) == 0:
                return np.array([])

            # Extract features using TorchReID
            with torch.no_grad():
                features = self.extractor(crops)

            # Convert to numpy and normalize
            features_np = features.cpu().numpy()

            # L2 normalize features
            return features_np / (np.linalg.norm(features_np, axis=1, keepdims=True) + 1e-8)

        except Exception as e:
            logger.error(f"Error extracting features: {e}")
            return None

    def compute_similarity(self, features1: np.ndarray, features2: np.ndarray) -> np.ndarray:
        """
        Compute cosine similarity between two sets of features

        Args:
            features1: First set of features (N, D)
            features2: Second set of features (M, D)

        Returns:
            Similarity matrix (N, M) with values in [0, 1]
        """
        if len(features1) == 0 or len(features2) == 0:
            return np.array([])

        # Compute cosine similarity
        similarity = np.dot(features1, features2.T)

        # Clip to [0, 1] range
        return np.clip(similarity, 0, 1)

    def compute_distance(self, features1: np.ndarray, features2: np.ndarray) -> np.ndarray:
        """
        Compute cosine distance between two sets of features

        Args:
            features1: First set of features (N, D)
            features2: Second set of features (M, D)

        Returns:
            Distance matrix (N, M) with values in [0, 1]
        """
        similarity = self.compute_similarity(features1, features2)
        return 1.0 - similarity

    def get_feature_dim(self) -> int:
        """Get the dimension of extracted features"""
        if (
            self.model_name.startswith("osnet_x0_25")
            or self.model_name.startswith("osnet_x1_0")
            or self.model_name.startswith("osnet_ain")
        ):
            return 512
        # Default dimension, actual may vary
        return 512

    def extract_single_feature(self, image: np.ndarray) -> np.ndarray | None:
        """
        Extract feature from a single image (convenience method)

        Args:
            image: Person crop image

        Returns:
            Feature vector (feature_dim,) or None
        """
        if self.extractor is None:
            return None

        try:
            with torch.no_grad():
                features = self.extractor([image])

            features_np = features.cpu().numpy()[0]

            # L2 normalize
            return features_np / (np.linalg.norm(features_np) + 1e-8)

        except Exception as e:
            logger.error(f"Error extracting single feature: {e}")
            return None

    def __call__(self, frame: np.ndarray, detections):
        """Allow the extractor to be called directly (for DeepSORT compatibility)"""
        return self.extract_features(frame, detections)

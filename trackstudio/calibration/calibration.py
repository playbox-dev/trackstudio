"""
Camera Calibration Module
Handles all camera calibration functionality for the vision system
"""

import json
import logging
import time
import traceback
from pathlib import Path
from typing import Any

import cv2
import numpy as np

logger = logging.getLogger(__name__)


class CameraCalibration:
    """Handles camera calibration for BEV transformation"""

    def __init__(self, calibration_file: str = "calibration_data.json"):
        # Convert to absolute path to avoid working directory issues
        self.calibration_file = str(Path(calibration_file).resolve())
        self.homography_matrices: dict[int, np.ndarray] = {}

        # Initialize default homography matrices
        self._initialize_default_homography()

        # Load existing calibration data
        self.load_calibration_data()

        logger.info("📐 Camera calibration module initialized")

    def _initialize_default_homography(self):
        """Initialize default homography matrices for cameras"""
        # Improved default homography matrices that preserve aspect ratios
        # Camera frame: 720x480, BEV canvas: 600x600
        # Scale factor to maintain aspect ratio: 600/720 = 0.833
        scale_x = 0.833  # Scale down to fit width
        scale_y = 1.25  # Scale up to account for perspective

        self.homography_matrices = {
            0: np.array(
                [  # Camera 0 (top-left) - better default transformation
                    [scale_x, 0.0, 50.0],  # Scale x and offset slightly
                    [0.0, scale_y, 50.0],  # Scale y and offset slightly
                    [0.0, 0.001, 1.0],  # Minimal perspective distortion
                ],
                dtype=np.float32,
            ),
            1: np.array(
                [  # Camera 1 (top-right)
                    [scale_x, 0.0, 150.0],  # More x offset for right camera
                    [0.0, scale_y, 50.0],
                    [0.0, 0.001, 1.0],
                ],
                dtype=np.float32,
            ),
            2: np.array(
                [  # Camera 2 (bottom-left)
                    [scale_x, 0.0, 50.0],
                    [0.0, scale_y, 350.0],  # Y offset for bottom row
                    [0.0, 0.001, 1.0],
                ],
                dtype=np.float32,
            ),
            3: np.array(
                [  # Camera 3 (bottom-right)
                    [scale_x, 0.0, 150.0],
                    [0.0, scale_y, 350.0],  # Both x and y offset
                    [0.0, 0.001, 1.0],
                ],
                dtype=np.float32,
            ),
        }

    def calibrate_camera(
        self,
        camera_id: int,
        image_points: list[tuple[float, float]],
        bev_points: list[tuple[float, float]],
        bev_size: int = 600,
    ) -> tuple[bool, str, np.ndarray | None]:
        """
        Calibrate camera using 4-point correspondence

        Args:
            camera_id: Camera ID (0 or 1)
            image_points: List of 4 points in image coordinates [(x, y), ...]
            bev_points: List of 4 corresponding points in normalized BEV coordinates [0-1]
            bev_size: Size of BEV map in pixels for transformation

        Returns:
            Tuple of (success, message, homography_matrix)
        """
        try:
            if len(image_points) != 4 or len(bev_points) != 4:
                return False, "Exactly 4 point pairs are required for calibration", None

            # Convert to numpy arrays
            img_pts = np.array(image_points, dtype=np.float32)
            bev_pts = np.array(bev_points, dtype=np.float32)

            # Convert normalized BEV points [0-1] to actual BEV coordinates
            bev_pts_pixel = bev_pts * bev_size

            # Compute homography matrix directly without aspect ratio correction
            # The frontend coordinate system now handles aspect ratios properly
            homography_matrix, mask = cv2.findHomography(img_pts, bev_pts_pixel, cv2.RANSAC)

            if homography_matrix is None:
                return False, "Failed to compute homography matrix. Check point correspondences.", None

            # Store the homography matrix
            self.homography_matrices[camera_id] = homography_matrix

            logger.info(f"📐 Camera {camera_id} calibrated successfully")
            return True, f"Camera {camera_id} calibrated successfully", homography_matrix

        except Exception as e:
            error_msg = f"Calibration failed: {str(e)}"
            logger.error(f"❌ {error_msg}")
            return False, error_msg, None

    def transform_image_with_homography(
        self, image: np.ndarray, camera_id: int, output_size: tuple[int, int] = (400, 400)
    ) -> np.ndarray | None:
        """
        Transform an image using the calibrated homography matrix

        Args:
            image: Input image to transform
            camera_id: Camera ID to get homography matrix for
            output_size: Output image size (width, height)

        Returns:
            Transformed image or None if no homography available
        """
        try:
            if camera_id not in self.homography_matrices:
                logger.warning(f"No homography matrix available for camera {camera_id}")
                return None

            homography_matrix = self.homography_matrices[camera_id]

            # Apply homography transformation
            return cv2.warpPerspective(image, homography_matrix, output_size)

        except Exception as e:
            logger.error(f"❌ Error transforming image: {e}")
            return None

    def transform_points_to_bev(self, points: list[tuple[float, float]], camera_id: int) -> list[tuple[float, float]]:
        """
        Transform image points to BEV coordinates using homography

        Args:
            points: List of (x, y) points in image coordinates
            camera_id: Camera ID to get homography matrix for

        Returns:
            List of transformed points in BEV coordinates
        """
        if camera_id not in self.homography_matrices or not points:
            return []

        try:
            homography_matrix = self.homography_matrices[camera_id]

            # Convert points to numpy array format expected by cv2.perspectiveTransform
            pts_array = np.array(points, dtype=np.float32).reshape(-1, 1, 2)

            # Apply homography transformation
            transformed_pts = cv2.perspectiveTransform(pts_array, homography_matrix)

            # Convert back to list of tuples
            return [(float(pt[0][0]), float(pt[0][1])) for pt in transformed_pts]

        except Exception as e:
            logger.error(f"❌ Error transforming points: {e}")
            return []

    def get_homography_matrix(self, camera_id: int) -> np.ndarray | None:
        """Get the current homography matrix for a camera"""
        return self.homography_matrices.get(camera_id, None)

    def update_homography(self, camera_id: int, homography_matrix: np.ndarray):
        """Update homography matrix for a specific camera"""
        self.homography_matrices[camera_id] = homography_matrix
        logger.info(f"📐 Updated homography matrix for camera {camera_id}")

    def save_calibration_data(
        self,
        camera_id: int,
        image_points: list[tuple[float, float]],
        bev_points: list[tuple[float, float]],
        homography_matrix: np.ndarray,
        bev_size: int = 400,
    ):
        """Save calibration data to file"""
        logger.info(f"🔧 Attempting to save calibration data for camera {camera_id} to {self.calibration_file}")
        try:
            # Load existing data WITHOUT updating in-memory matrices
            calibration_data = {}
            if Path(self.calibration_file).exists():
                logger.info(f"📖 Loading existing calibration data from {self.calibration_file}")
                with Path(self.calibration_file).open() as f:
                    calibration_data = json.load(f)
            else:
                logger.info(f"📝 Creating new calibration data file at {self.calibration_file}")

            # Update with new calibration
            calibration_data[f"camera{camera_id}"] = {
                "homography_matrix": homography_matrix.tolist(),
                "image_points": image_points,
                "bev_points": bev_points,
                "bev_size": bev_size,
                "calibrated_at": time.time(),
            }

            # Save to file
            logger.info(f"💾 Writing calibration data to {self.calibration_file}")
            with Path(self.calibration_file).open("w") as f:
                json.dump(calibration_data, f, indent=2)

            logger.info(f"✅ Successfully saved calibration data for camera {camera_id} to {self.calibration_file}")

        except Exception as e:
            logger.error(f"❌ Error saving calibration data to {self.calibration_file}: {e}")

            logger.error(f"📍 Traceback: {traceback.format_exc()}")

    def load_calibration_data(self) -> dict:
        """Load calibration data from file and update homography matrices"""
        if Path(self.calibration_file).exists():
            try:
                with Path(self.calibration_file).open() as f:
                    data = json.load(f)

                # Load homography matrices
                for camera_key, calibration in data.items():
                    if camera_key.startswith("camera") and "homography_matrix" in calibration:
                        camera_id = int(camera_key.replace("camera", ""))
                        matrix = np.array(calibration["homography_matrix"], dtype=np.float32)
                        self.homography_matrices[camera_id] = matrix
                        logger.info(f"📐 Loaded homography matrix for camera {camera_id}")

                return data

            except Exception as e:
                logger.error(f"❌ Error loading calibration file: {e}")
                return {}

        return {}

    def clear_calibration_data(self):
        """Clear all calibration data and reset to defaults"""
        try:
            if Path(self.calibration_file).exists():
                Path(self.calibration_file).unlink()

            # Reset homography matrices to defaults
            self._initialize_default_homography()

            logger.info("🗑️ Cleared all calibration data")

        except Exception as e:
            logger.error(f"❌ Error clearing calibration data: {e}")

    def get_calibration_status(self) -> dict[str, Any]:
        """Get calibration status for all cameras"""
        calibration_data = self.load_calibration_data()

        return {
            "camera0": {
                "calibrated": "camera0" in calibration_data,
                "calibrated_at": calibration_data.get("camera0", {}).get("calibrated_at", None),
                "has_homography": 0 in self.homography_matrices,
            },
            "camera1": {
                "calibrated": "camera1" in calibration_data,
                "calibrated_at": calibration_data.get("camera1", {}).get("calibrated_at", None),
                "has_homography": 1 in self.homography_matrices,
            },
            "camera2": {
                "calibrated": "camera2" in calibration_data,
                "calibrated_at": calibration_data.get("camera2", {}).get("calibrated_at", None),
                "has_homography": 2 in self.homography_matrices,
            },
            "camera3": {
                "calibrated": "camera3" in calibration_data,
                "calibrated_at": calibration_data.get("camera3", {}).get("calibrated_at", None),
                "has_homography": 3 in self.homography_matrices,
            },
        }

    def is_camera_calibrated(self, camera_id: int) -> bool:
        """Check if a camera is properly calibrated"""
        calibration_data = self.load_calibration_data()
        return f"camera{camera_id}" in calibration_data and camera_id in self.homography_matrices

"""
Camera Calibration Module
Handles all camera calibration functionality for the vision system
"""

import logging
import numpy as np
import cv2
import time
import json
import os
from typing import Dict, List, Tuple, Optional, Any

# Assuming ServerConfig is in the same package (e.g., your_project_name.config)
from ..core.config import ServerConfig

logger = logging.getLogger(__name__)

class CameraCalibration:
    """
    Handles camera calibration for BEV transformation and intrinsic (undistortion) parameters.
    Homography matrices are loaded from `calibration_file`.
    Intrinsic parameters are loaded from paths specified in `ServerConfig.CALIBRATION_FILES`.
    """
    
    def __init__(self, calibration_file: str = "calibration_data.json"):
        # Path for BEV/Homography calibration data
        self.calibration_file = calibration_file
        self.homography_matrices: Dict[int, np.ndarray] = {}
        
        # Dictionary to store intrinsic calibration data {stream_id: loaded_json_data}
        self.intrinsic_calibration_data: Dict[int, Dict[str, Any]] = {}

        # Initialize default homography matrices (BEV)
        self._initialize_default_homography()
        
        # Load existing homography calibration data from self.calibration_file
        self.load_homography_calibration_data()
        
        # NEW: Load intrinsic calibration data based on ServerConfig
        self._load_intrinsic_from_server_config()
        
        logger.info("📐 Camera calibration module initialized.")
    
    def _initialize_default_homography(self):
        """Initialize default homography matrices for cameras for BEV transformation."""
        # Improved default homography matrices that preserve aspect ratios
        # Camera frame: 720x480, BEV canvas: 600x600
        # Scale factor to maintain aspect ratio: 600/720 = 0.833
        scale_x = 0.833   # Scale down to fit width
        scale_y = 1.25    # Scale up to account for perspective (example)
        
        self.homography_matrices = {
            0: np.array([   # Camera 0 (top-left) - better default transformation
                [scale_x, 0.0, 50.0],      # Scale x and offset slightly
                [0.0, scale_y, 50.0],      # Scale y and offset slightly    
                [0.0, 0.001, 1.0]          # Minimal perspective distortion
            ], dtype=np.float32),
            1: np.array([   # Camera 1 (top-right)
                [scale_x, 0.0, 150.0],     # More x offset for right camera
                [0.0, scale_y, 50.0],     
                [0.0, 0.001, 1.0]
            ], dtype=np.float32),
            2: np.array([   # Camera 2 (bottom-left)
                [scale_x, 0.0, 50.0],      
                [0.0, scale_y, 350.0],     # Y offset for bottom row
                [0.0, 0.001, 1.0]
            ], dtype=np.float32),
            3: np.array([   # Camera 3 (bottom-right)
                [scale_x, 0.0, 150.0],     
                [0.0, scale_y, 350.0],     # Both x and y offset
                [0.0, 0.001, 1.0]
            ], dtype=np.float32)
        }
    
    def _load_intrinsic_from_server_config(self):
        """
        NEW: Loads intrinsic calibration data from files specified in ServerConfig.CALIBRATION_FILES.
        This data is stored in self.intrinsic_calibration_data.
        """
        if ServerConfig.CALIBRATION_FILES:
            logger.info(f"Loading intrinsic calibration files from ServerConfig: {ServerConfig.CALIBRATION_FILES}")
            for stream_id, file_path in ServerConfig.CALIBRATION_FILES.items():
                try:
                    if os.path.exists(file_path):
                        with open(file_path, 'r') as f:
                            data = json.load(f)
                            self.intrinsic_calibration_data[stream_id] = data
                            logger.info(f"✅ Loaded intrinsic data for stream {stream_id} from {file_path}")
                    else:
                        logger.warning(f"Intrinsic calibration file not found for stream {stream_id}: {file_path}")
                except json.JSONDecodeError:
                    logger.error(f"Invalid JSON in intrinsic calibration file for stream {stream_id}: {file_path}")
                except Exception as e:
                    logger.error(f"Error loading intrinsic calibration for stream {stream_id} from {file_path}: {e}")
        else:
            logger.info("No intrinsic calibration files specified in ServerConfig.CALIBRATION_FILES.")

    def calibrate_camera(self, camera_id: int, image_points: List[Tuple[float, float]], 
                         bev_points: List[Tuple[float, float]], bev_size: int = 600) -> Tuple[bool, str, Optional[np.ndarray]]:
        """
        Calibrate camera for BEV transformation using 4-point correspondence.
        
        Args:
            camera_id: Camera ID (0-3)
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
            homography_matrix, mask = cv2.findHomography(img_pts, bev_pts_pixel, cv2.RANSAC)
            
            if homography_matrix is None:
                return False, "Failed to compute homography matrix. Check point correspondences.", None
            
            # Store the homography matrix
            self.homography_matrices[camera_id] = homography_matrix
            
            logger.info(f"📐 Camera {camera_id} BEV calibrated successfully")
            return True, f"Camera {camera_id} BEV calibrated successfully", homography_matrix
            
        except Exception as e:
            error_msg = f"BEV calibration failed: {str(e)}"
            logger.error(f"❌ {error_msg}")
            return False, error_msg, None
    
    def transform_image_with_homography(self, image: np.ndarray, camera_id: int, 
                                        output_size: Tuple[int, int] = (400, 400)) -> Optional[np.ndarray]:
        """
        Transform an image using the calibrated homography matrix (for BEV).
        
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
            transformed_image = cv2.warpPerspective(image, homography_matrix, output_size)
            
            return transformed_image
            
        except Exception as e:
            logger.error(f"❌ Error transforming image with homography: {e}")
            return None
    
    def transform_points_to_bev(self, points: List[Tuple[float, float]], camera_id: int) -> List[Tuple[float, float]]:
        """
        Transform image points to BEV coordinates using homography.
        
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
            logger.error(f"❌ Error transforming points to BEV: {e}")
            return []
    
    def get_homography_matrix(self, camera_id: int) -> Optional[np.ndarray]:
        """Get the current homography matrix for a camera"""
        return self.homography_matrices.get(camera_id, None)
    
    def update_homography(self, camera_id: int, homography_matrix: np.ndarray):
        """Update homography matrix for a specific camera (for BEV)."""
        self.homography_matrices[camera_id] = homography_matrix
        logger.info(f"📐 Updated homography matrix for camera {camera_id}")
    
    def save_calibration_data(self, camera_id: int, image_points: List[Tuple[float, float]], 
                              bev_points: List[Tuple[float, float]], homography_matrix: np.ndarray,
                              bev_size: int = 400):
        """Save BEV calibration data to file (homography matrices, points)."""
        try:
            # Load existing data WITHOUT updating in-memory matrices
            calibration_data = {}
            if os.path.exists(self.calibration_file):
                with open(self.calibration_file, 'r') as f:
                    calibration_data = json.load(f)
            
            # Update with new calibration for this camera
            # Store camera ID as string key in JSON for consistency
            calibration_data[f"camera{camera_id}"] = {
                "homography_matrix": homography_matrix.tolist(),
                "image_points": image_points,
                "bev_points": bev_points,
                "bev_size": bev_size,
                "calibrated_at": time.time()
            }
            
            # Save to file
            with open(self.calibration_file, 'w') as f:
                json.dump(calibration_data, f, indent=2)
            
            logger.info(f"💾 Saved BEV calibration data for camera {camera_id} to {self.calibration_file}")
            
        except Exception as e:
            logger.error(f"❌ Error saving BEV calibration data: {e}")
    
    def load_homography_calibration_data(self) -> Dict:
        """Load homography calibration data from file and update in-memory matrices."""
        if os.path.exists(self.calibration_file):
            try:
                with open(self.calibration_file, 'r') as f:
                    data = json.load(f)
                
                # Load homography matrices from the file
                for camera_key, calibration in data.items():
                    if camera_key.startswith('camera') and 'homography_matrix' in calibration:
                        # Extract integer camera_id from string key (e.g., "camera0" -> 0)
                        camera_id = int(camera_key.replace('camera', ''))
                        matrix = np.array(calibration['homography_matrix'], dtype=np.float32)
                        self.homography_matrices[camera_id] = matrix
                        logger.info(f"📐 Loaded homography matrix for camera {camera_id} from {self.calibration_file}")
                
                return data
                
            except json.JSONDecodeError:
                logger.error(f"❌ Invalid JSON in homography calibration file: {self.calibration_file}. Returning empty data.")
                return {}
            except Exception as e:
                logger.error(f"❌ Error loading homography calibration file: {e}. Returning empty data.")
                return {}
        
        logger.info(f"No homography calibration file found at {self.calibration_file}. Using default matrices.")
        return {}
    
    def clear_calibration_data(self):
        """Clear all calibration data (homography and intrinsic) and reset homographies to defaults."""
        try:
            if os.path.exists(self.calibration_file):
                os.remove(self.calibration_file)
            
            # Reset homography matrices to defaults
            self._initialize_default_homography()
            
            # Clear intrinsic calibration data
            self.intrinsic_calibration_data = {}

            logger.info("🗑️ Cleared all calibration data (homography and intrinsic).")
            
        except Exception as e:
            logger.error(f"❌ Error clearing calibration data: {e}")
    
    def get_calibration_status(self) -> Dict[str, Any]:
        """Get calibration status for all cameras (including both BEV and intrinsic)."""
        # Reload homography data to ensure status is fresh from disk
        homography_data_from_file = self.load_homography_calibration_data() 
        
        status = {}
        # Iterate over all possible stream IDs (based on default homography keys or ServerConfig enabled streams)
        all_stream_ids = sorted(list(set(self.homography_matrices.keys()) | set(ServerConfig.get_enabled_streams())))

        for stream_id in all_stream_ids:
            camera_key = f"camera{stream_id}"
            
            # Check BEV calibration status
            bev_calibrated = camera_key in homography_data_from_file and stream_id in self.homography_matrices
            bev_calibrated_at = homography_data_from_file.get(camera_key, {}).get("calibrated_at", None)

            # Check intrinsic calibration status
            intrinsic_calibrated = stream_id in self.intrinsic_calibration_data
            intrinsic_data_timestamp = self.intrinsic_calibration_data.get(stream_id, {}).get("timestamp", None) # Assuming timestamp in intrinsic JSON
            
            status[camera_key] = {
                "bev_calibrated": bev_calibrated,
                "bev_calibrated_at": bev_calibrated_at,
                "has_homography_matrix": stream_id in self.homography_matrices,
                "intrinsic_calibrated": intrinsic_calibrated,
                "intrinsic_data_timestamp": intrinsic_data_timestamp # Show when the intrinsic data was generated
            }
        
        return status
    
    def is_camera_calibrated(self, camera_id: int) -> bool:
        """
        Check if a camera has both BEV homography and intrinsic calibration loaded.
        (You might adjust this logic if only one type of calibration is strictly required).
        """
        # Checks if BEV homography is loaded AND intrinsic data is loaded
        return camera_id in self.homography_matrices and camera_id in self.intrinsic_calibration_data

    def load_intrinsic_calibration(self, camera_id: int) -> Tuple[Optional[np.ndarray], Optional[np.ndarray], Tuple[int, int], Optional[np.ndarray]]:
        """
        Load intrinsic calibration (K matrix and distortion coefficients) for a given camera_id.
        This method now retrieves data from `self.intrinsic_calibration_data`
        which was populated by `_load_intrinsic_from_server_config()`.
        
        Returns:
            Tuple of (K, D, image_size, new_K_from_file)
            Returns (None, None, (2560, 1440), None) on failure or if data is not found.
        """
        data = self.intrinsic_calibration_data.get(camera_id)
        if data:
            try:
                K = np.array(data['camera_matrix_K'], dtype=np.float32)
                D = np.array(data['distortion_coefficients_D'], dtype=np.float32).flatten()
                image_size = (data['image_width'], data['image_height'])

                new_K_from_file = None
                if 'new_camera_matrix' in data:
                    new_K_from_file = np.array(data['new_camera_matrix'], dtype=np.float32)
                
                logger.info(f"📷 Loaded intrinsic calibration for camera {camera_id} from in-memory data.")
                logger.info(f"   Image size: {image_size[0]}x{image_size[1]}")
                logger.info(f"   Distortion coefficients: {len(D)} (model: {'fisheye' if len(D) == 4 else ('rational' if len(D) > 5 else 'standard')})")
                
                return K, D, image_size, new_K_from_file
            
            except KeyError as e:
                logger.warning(f"Intrinsic data for camera {camera_id} missing key: {e}. Data structure might be incorrect.")
                return None, None, (2560, 1440), None # Return default size and None for matrices
            except Exception as e:
                logger.warning(f"Error parsing intrinsic calibration data for camera {camera_id}: {e}")
                return None, None, (2560, 1440), None # Return default size and None for matrices
        
        logger.warning(f"No intrinsic calibration data found for camera {camera_id} in in-memory storage.")
        return None, None, (2560, 1440), None # Default size
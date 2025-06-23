"""
Camera Calibration API
Handles frame capture and camera-to-BEV calibration
"""

import base64
import logging

import cv2
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..stream_combiner import stream_combiner_manager

logger = logging.getLogger(__name__)
router = APIRouter()

# Vision API instance will be set by TrackStudioApp
vision_api = None


def set_vision_api(api):
    """Set the VisionAPI instance to use"""
    global vision_api  # noqa: PLW0603
    vision_api = api
    logger.info(f"🔗 Calibration API received VisionAPI with {api.tracker.__class__.__name__}")


class PointPair(BaseModel):
    image_point: tuple[float, float]  # (x, y) in pixel coordinates
    bev_point: tuple[float, float]  # (x, y) in normalized BEV coordinates [0-1]


class CalibrationRequest(BaseModel):
    camera_id: int  # 0, 1, 2, or 3
    point_pairs: list[PointPair]  # 4 point pairs for homography


class CalibrationResponse(BaseModel):
    success: bool
    message: str
    transformed_image_base64: str | None = None
    homography_matrix: list[list[float]] | None = None


@router.get("/capture-frames")
async def capture_frames():
    """Capture single frames from all active cameras"""
    try:
        # Get latest frame from stream combiner
        combined_frame = stream_combiner_manager.get_latest_frame()

        if combined_frame is None:
            raise HTTPException(status_code=404, detail="No frames available. Start the combined stream first.")

        # Determine layout based on frame dimensions
        height, width = combined_frame.shape[:2]

        # Encode frames to base64
        def frame_to_base64(frame):
            _, buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 90])
            return base64.b64encode(buffer.tobytes()).decode("utf-8")

        if height == 480:  # 2x1 layout (2 cameras)
            # Split into left and right halves
            camera0_frame = combined_frame[:, : width // 2]  # Left half
            camera1_frame = combined_frame[:, width // 2 :]  # Right half

            result = {
                "success": True,
                "camera0_frame": frame_to_base64(camera0_frame),
                "camera1_frame": frame_to_base64(camera1_frame),
                "frame_width": camera0_frame.shape[1],
                "frame_height": camera0_frame.shape[0],
                "num_cameras": 2,
            }
        else:  # 2x2 layout (3-4 cameras)
            # Split into 2x2 grid
            half_width = width // 2
            half_height = height // 2

            camera0_frame = combined_frame[:half_height, :half_width]  # Top-left
            camera1_frame = combined_frame[:half_height, half_width:]  # Top-right
            camera2_frame = combined_frame[half_height:, :half_width]  # Bottom-left
            camera3_frame = combined_frame[half_height:, half_width:]  # Bottom-right

            # Determine actual number of cameras based on combined frame manager
            num_cameras = 4  # Default to 4 for 2x2 layout
            try:
                # Try to get actual number from the combiner manager
                if hasattr(stream_combiner_manager, "track") and stream_combiner_manager.track:
                    num_cameras = len(stream_combiner_manager.track.active_stream_ids)
            except AttributeError:
                pass  # Fallback to 4

            result = {
                "success": True,
                "camera0_frame": frame_to_base64(camera0_frame),
                "camera1_frame": frame_to_base64(camera1_frame),
                "camera2_frame": frame_to_base64(camera2_frame),
                "camera3_frame": frame_to_base64(camera3_frame),
                "frame_width": camera0_frame.shape[1],
                "frame_height": camera0_frame.shape[0],
                "num_cameras": num_cameras,
            }

        return result

    except Exception as e:
        logger.error(f"Error capturing frames: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to capture frames: {str(e)}") from e


@router.post("/calibrate", response_model=CalibrationResponse)
async def calibrate_camera(request: CalibrationRequest):
    """Calibrate camera using 4-point correspondence"""
    try:
        if not vision_api:
            raise HTTPException(status_code=503, detail="Vision API not available")

        # Get frame dimensions for later use
        combined_frame = stream_combiner_manager.get_latest_frame()
        if combined_frame is None:
            raise HTTPException(status_code=404, detail="No frames available. Start the combined stream first.")

        height, width = combined_frame.shape[:2]
        camera_frame_width = width // 2  # Each camera gets half the combined frame width
        camera_frame_height = height

        # Image points are already in pixel coordinates, use directly
        image_points = [(pair.image_point[0], pair.image_point[1]) for pair in request.point_pairs]

        # BEV points are already normalized [0-1] as expected
        bev_points = [(pair.bev_point[0], pair.bev_point[1]) for pair in request.point_pairs]

        # Use vision API to perform calibration (600x600 to match frontend BEV canvas)

        success, message, homography_matrix = vision_api.calibrate_camera(
            request.camera_id, image_points, bev_points, bev_size=600
        )

        if not success or homography_matrix is None:
            raise HTTPException(status_code=400, detail=message)

        # Save calibration data using vision API
        vision_api.save_calibration_data(request.camera_id, image_points, bev_points, homography_matrix, bev_size=600)

        # Get a test frame to show transformation result
        transformed_image_base64 = None

        # Extract camera frame (we already have combined_frame from earlier)
        # Support 2x2 grid layout for 3-4 cameras or 2x1 for 2 cameras
        if height == 480:  # 2x1 layout (2 cameras)
            if request.camera_id == 0:
                camera_frame = combined_frame[:, :camera_frame_width]  # Left half
            else:
                camera_frame = combined_frame[:, camera_frame_width:]  # Right half
        else:  # 2x2 layout (3-4 cameras)
            camera_frame_width = width // 2
            camera_frame_height = height // 2
            if request.camera_id == 0:
                camera_frame = combined_frame[:camera_frame_height, :camera_frame_width]  # Top-left
            elif request.camera_id == 1:
                camera_frame = combined_frame[:camera_frame_height, camera_frame_width:]  # Top-right
            elif request.camera_id == 2:
                camera_frame = combined_frame[camera_frame_height:, :camera_frame_width]  # Bottom-left
            else:  # camera_id == 3
                camera_frame = combined_frame[camera_frame_height:, camera_frame_width:]  # Bottom-right

        # Use vision API to transform the image
        transformed_frame = vision_api.transform_image_with_homography(
            camera_frame,
            request.camera_id,
            output_size=(600, 600),  # Match frontend canvas size
        )

        if transformed_frame is not None:
            # Encode to base64
            _, buffer = cv2.imencode(".jpg", transformed_frame, [cv2.IMWRITE_JPEG_QUALITY, 90])
            transformed_image_base64 = base64.b64encode(buffer.tobytes()).decode("utf-8")
        else:
            logger.warning(f"Transformation failed for camera {request.camera_id}")

        logger.info(f"Camera {request.camera_id} calibrated successfully")

        return CalibrationResponse(
            success=True,
            message=message,
            transformed_image_base64=transformed_image_base64,
            homography_matrix=homography_matrix.tolist() if homography_matrix is not None else None,
        )

    except Exception as e:
        logger.error(f"Calibration error: {e}")
        raise HTTPException(status_code=500, detail=f"Calibration failed: {str(e)}") from e


@router.get("/calibration-data")
async def get_calibration_data():
    """Get current calibration data"""
    try:
        if not vision_api:
            raise HTTPException(status_code=503, detail="Vision API not available")

        data = vision_api.load_calibration_data()
        status = vision_api.get_calibration_status()

        return {"success": True, "calibration_data": data, "status": status}
    except Exception as e:
        logger.error(f"Error loading calibration data: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to load calibration data: {str(e)}") from e


@router.delete("/calibration-data")
async def clear_calibration_data():
    """Clear all calibration data"""
    try:
        if not vision_api:
            raise HTTPException(status_code=503, detail="Vision API not available")

        vision_api.clear_calibration_data()
        return {"success": True, "message": "Calibration data cleared"}
    except Exception as e:
        logger.error(f"Error clearing calibration data: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to clear calibration data: {str(e)}") from e


@router.get("/debug-transform-calibration-points")
async def debug_transform_calibration_points():
    """
    Debug endpoint: Transform calibration image points through backend homography
    to compare with frontend reference points
    """
    try:
        if not vision_api:
            raise HTTPException(status_code=503, detail="Vision API not available")

        calibration_data = vision_api.load_calibration_data()

        if not calibration_data:
            return {"success": True, "message": "No calibration data available", "transformed_points": {}}

        transformed_points = {}

        for camera_key, camera_data in calibration_data.items():
            if camera_key.startswith("camera") and "image_points" in camera_data:
                camera_id = int(camera_key.replace("camera", ""))
                image_points = camera_data["image_points"]

                # Transform the image points through the backend homography
                calibration = getattr(vision_api.tracker, "calibration", None)
                backend_bev_points = calibration.transform_points_to_bev(image_points, camera_id) if calibration else []

                # Get the original BEV reference points for comparison
                original_bev_points = camera_data.get("bev_points", [])

                transformed_points[camera_key] = {
                    "camera_id": camera_id,
                    "image_points": image_points,
                    "original_bev_points_normalized": original_bev_points,  # [0-1] range
                    "original_bev_points_pixels": [
                        (p[0] * 600, p[1] * 600) for p in original_bev_points
                    ],  # Scaled to pixels
                    "backend_transformed_pixels": backend_bev_points,  # Direct from homography
                    "differences": [],
                }

                # Calculate differences between reference and transformed points
                if len(original_bev_points) == len(backend_bev_points):
                    for i, (orig_norm, backend_px) in enumerate(
                        zip(original_bev_points, backend_bev_points, strict=False)
                    ):
                        orig_px = (orig_norm[0] * 600, orig_norm[1] * 600)
                        diff_x = backend_px[0] - orig_px[0]
                        diff_y = backend_px[1] - orig_px[1]
                        distance = (diff_x**2 + diff_y**2) ** 0.5

                        transformed_points[camera_key]["differences"].append(
                            {
                                "point_index": i,
                                "reference_pixels": orig_px,
                                "backend_pixels": backend_px,
                                "difference_pixels": (diff_x, diff_y),
                                "distance_pixels": distance,
                            }
                        )

        return {
            "success": True,
            "message": "Calibration points transformed for debugging",
            "transformed_points": transformed_points,
        }

    except Exception as e:
        logger.error(f"Error transforming calibration points: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to transform calibration points: {str(e)}") from e

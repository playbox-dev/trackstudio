import logging
import time
from collections.abc import Generator
from pathlib import Path

import cv2
import numpy as np
import pytest

logger = logging.getLogger(__name__)


@pytest.fixture
def combined_stream_reader():
    """
    Fixture that creates a simulated combined stream by reading directly from video files.
    No WebRTC system required - just reads cam1.mp4 and cam2.mp4 and combines them.
    """

    # Check for video files
    video_path_0 = Path("tests/cam1.mp4")
    video_path_1 = Path("tests/cam2.mp4")

    if not video_path_0.exists():
        pytest.skip(f"Video file not found: {video_path_0}")
    if not video_path_1.exists():
        pytest.skip(f"Video file not found: {video_path_1}")

    class MockStreamReader:
        """Mock stream reader that combines two video files"""

        def __init__(self):
            self.cap0 = cv2.VideoCapture(str(video_path_0))
            self.cap1 = cv2.VideoCapture(str(video_path_1))
            self.frame_count = 0

            if not self.cap0.isOpened():
                pytest.skip(f"Could not open video file: {video_path_0}")
            if not self.cap1.isOpened():
                pytest.skip(f"Could not open video file: {video_path_1}")

            logger.info(f"✅ Opened video files: {video_path_0.name} and {video_path_1.name}")

        def get_frame(self) -> np.ndarray | None:
            """Get a combined frame by reading from both video files"""
            ret0, frame0 = self.cap0.read()
            ret1, frame1 = self.cap1.read()

            if not ret0 or not ret1:
                # If we reach end of video, restart from beginning
                self.cap0.set(cv2.CAP_PROP_POS_FRAMES, 0)
                self.cap1.set(cv2.CAP_PROP_POS_FRAMES, 0)
                ret0, frame0 = self.cap0.read()
                ret1, frame1 = self.cap1.read()

                if not ret0 or not ret1:
                    return None

            # Resize frames to expected size (720x480 each)
            frame0 = cv2.resize(frame0, (720, 480))
            frame1 = cv2.resize(frame1, (720, 480))

            # Combine side by side (1440x480 total)
            combined_frame = np.hstack([frame0, frame1])

            self.frame_count += 1
            return combined_frame

        def get_frame_split(self) -> tuple[np.ndarray | None, np.ndarray | None]:
            """Get individual camera frames (already available from get_frame logic)"""
            ret0, frame0 = self.cap0.read()
            ret1, frame1 = self.cap1.read()

            if not ret0 or not ret1:
                # If we reach end of video, restart from beginning
                self.cap0.set(cv2.CAP_PROP_POS_FRAMES, 0)
                self.cap1.set(cv2.CAP_PROP_POS_FRAMES, 0)
                ret0, frame0 = self.cap0.read()
                ret1, frame1 = self.cap1.read()

                if not ret0 or not ret1:
                    return None, None

            # Resize frames to expected size
            frame0 = cv2.resize(frame0, (720, 480))
            frame1 = cv2.resize(frame1, (720, 480))

            return frame0, frame1

        def frame_generator(self, max_frames: int = 100, fps: float = 15.0) -> Generator[np.ndarray, None, None]:
            """Generator that yields combined frames at specified FPS"""
            frame_count = 0
            frame_time = 1.0 / fps  # Time between frames

            while frame_count < max_frames:
                start_time = time.time()

                frame = self.get_frame()
                if frame is not None:
                    yield frame
                    frame_count += 1

                    # Maintain frame rate
                    elapsed = time.time() - start_time
                    sleep_time = max(0, frame_time - elapsed)
                    if sleep_time > 0:
                        time.sleep(sleep_time)
                else:
                    break

        def wait_for_frame(self, timeout_seconds: int = 10) -> np.ndarray | None:
            """Get a frame immediately (always available from video files)"""
            return self.get_frame()

        def get_stream_info(self) -> dict:
            """Get information about the mock stream"""
            # Get video properties
            total_frames_0 = int(self.cap0.get(cv2.CAP_PROP_FRAME_COUNT))
            total_frames_1 = int(self.cap1.get(cv2.CAP_PROP_FRAME_COUNT))
            fps_0 = self.cap0.get(cv2.CAP_PROP_FPS)
            fps_1 = self.cap1.get(cv2.CAP_PROP_FPS)

            return {
                "is_running": True,
                "resolution": (1440, 480),  # Combined resolution
                "individual_resolution": (720, 480),
                "expected_fps": 15,
                "source_files": [str(video_path_0), str(video_path_1)],
                "total_frames": min(total_frames_0, total_frames_1),
                "source_fps": [fps_0, fps_1],
                "current_frame": self.frame_count,
            }

        def cleanup(self):
            """Release video captures"""
            if self.cap0:
                self.cap0.release()
            if self.cap1:
                self.cap1.release()

    reader = MockStreamReader()

    # Test that we can get a frame
    test_frame = reader.get_frame()
    if test_frame is None:
        pytest.skip("Could not read frames from video files")

    logger.info(f"✅ Mock combined stream reader ready - frame shape: {test_frame.shape}")

    yield reader

    # Cleanup
    reader.cleanup()


@pytest.fixture
def vision_test_frames(combined_stream_reader):
    """
    Fixture that provides a batch of frames for vision pipeline testing.
    Returns a list of frames ready for vision processing.
    """

    frames = []
    max_frames = 10  # Get 10 frames for testing

    logger.info(f"🎬 Collecting {max_frames} frames for vision testing...")

    for i, frame in enumerate(combined_stream_reader.frame_generator(max_frames)):
        frames.append(frame)
        if i == 0:
            logger.info(f"📊 Frame info: shape={frame.shape}, dtype={frame.dtype}")

    if len(frames) == 0:
        pytest.skip("No frames collected for vision testing")

    logger.info(f"✅ Collected {len(frames)} frames for vision testing")

    # At this point, frames is guaranteed to have at least one element
    first_frame = frames[0]

    return {
        "frames": frames,
        "count": len(frames),
        "shape": first_frame.shape,
        "combined_resolution": (1440, 480),
        "individual_resolution": (720, 480),
    }


@pytest.fixture
def vision_single_frame(combined_stream_reader):
    """
    Simple fixture that provides a single frame for quick vision testing.
    """
    frame = combined_stream_reader.get_frame()
    if frame is None:
        pytest.skip("Could not get a frame for vision testing")

    return {
        "frame": frame,
        "shape": frame.shape,
        "combined_resolution": (1440, 480),
        "individual_resolution": (720, 480),
    }


@pytest.fixture
def individual_camera_frames(combined_stream_reader):
    """
    Fixture that provides individual camera frames (split) for testing.
    """
    camera0_frame, camera1_frame = combined_stream_reader.get_frame_split()

    if camera0_frame is None or camera1_frame is None:
        pytest.skip("Could not get individual camera frames")

    return {
        "camera0": camera0_frame,
        "camera1": camera1_frame,
        "camera0_shape": camera0_frame.shape,
        "camera1_shape": camera1_frame.shape,
        "individual_resolution": (720, 480),
    }

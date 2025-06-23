"""
Stream Combiner Manager
Simple OpenCV-based stream capture and combination

Uses direct RTMP/RTSP URLs with OpenCV's VideoCapture (FFmpeg backend)
"""

import asyncio
import contextlib
import logging
import time
from collections import deque
from fractions import Fraction
from typing import Optional

import cv2
import numpy as np
from aiortc import VideoStreamTrack

from .config import ServerConfig
from .vision_api import VisionResult

logger = logging.getLogger(__name__)

# Vision API will be set by TrackStudioApp
vision_api = None


class StreamFrame:
    """Container for a frame with its capture timestamp and stream ID"""

    def __init__(self, frame: np.ndarray, timestamp: float, stream_id: int):
        self.frame = frame
        self.timestamp = timestamp
        self.stream_id = stream_id


class StreamCombinerTrack(VideoStreamTrack):
    """VideoTrack that captures individual RTMP/RTSP streams and combines them with manual delays"""

    def __init__(self):
        super().__init__()

        # Individual stream captures
        self.stream_caps = {}  # {stream_id: cv2.VideoCapture}
        self.is_running = False

        # Initialize timing attributes required by aiortc
        self._timestamp = 0
        self._start_time = None

        # Simple vision processing flag
        self.vision_processing = False

        # Get active streams from config
        self.enabled_streams = ServerConfig.get_enabled_streams()
        self.active_stream_ids = [stream["id"] for stream in self.enabled_streams]

        # Time-shift delay buffer system (smooth delayed video) - dynamic streams
        self.stream_delays = dict.fromkeys(self.active_stream_ids, 0)
        self.frame_buffers = {stream_id: deque() for stream_id in self.active_stream_ids}
        self.last_frames = dict.fromkeys(self.active_stream_ids)

        # Stream status tracking
        self.stream_status = dict.fromkeys(self.active_stream_ids, "initializing")  # initializing, ready, error
        self.stream_init_timeout = {
            stream_id: time.time() + 30.0 for stream_id in self.active_stream_ids
        }  # 30 second timeout

        # Frame read statistics for debugging flickering
        self.frame_read_stats = {
            stream_id: {"success": 0, "failures": 0, "last_failure_time": 0} for stream_id in self.active_stream_ids
        }
        self.stats_report_interval = 100  # Report every 100 frames
        self.frame_counter_for_stats = 0

        logger.info(f"📌 Initialized per-stream delays: {self.stream_delays}")

        # FPS calculation
        self.fps = 30  # target FPS
        self.frame_count = 0
        self.last_fps_time = time.time()
        self.measured_fps = 0.0

        # Vision processor result
        self.latest_vision_result: VisionResult | None = None

        # Background vision processing task

        logger.info("🎬 Video track created - streams will be initialized on-demand")

        # Vision tracking is now opt-in - must be explicitly enabled via API
        logger.info("🧠 Vision tracking is disabled by default - enable via /api/vision/enable if needed")

    def _create_status_frame(self, width: int, height: int, stream_id: int, status: str) -> np.ndarray:
        """Create a status frame with text overlay"""
        # Create black frame
        frame = np.zeros((height, width, 3), dtype=np.uint8)

        # Add some color for visual feedback
        if status == "initializing":
            # Blue tint for initializing
            frame[:, :, 0] = 30  # Blue channel
            text = f"Initializing Stream {stream_id}..."
            color = (255, 255, 0)  # Yellow text
        elif status == "preparing":
            # Green tint for preparing
            frame[:, :, 1] = 30  # Green channel
            text = f"Preparing Stream {stream_id}..."
            color = (0, 255, 255)  # Cyan text
        elif status == "timeout":
            # Red tint for timeout
            frame[:, :, 2] = 50  # Red channel
            text = f"Stream {stream_id} Timeout"
            color = (0, 0, 255)  # Red text
        elif status == "error":
            # Red tint for error
            frame[:, :, 2] = 50  # Red channel
            text = f"Stream {stream_id} Error"
            color = (0, 0, 255)  # Red text
        elif status == "reconnecting":
            # Orange tint for reconnecting
            frame[:, :, 2] = 30  # Red channel
            frame[:, :, 1] = 15  # Green channel
            text = f"Reconnecting Stream {stream_id}..."
            color = (0, 165, 255)  # Orange text
        else:
            text = f"Stream {stream_id} - {status}"
            color = (255, 255, 255)  # White text

        try:
            import cv2  # noqa: PLC0415

            # Add main text
            font = cv2.FONT_HERSHEY_SIMPLEX
            font_scale = 0.8
            thickness = 2

            # Get text size for centering
            (text_width, text_height), baseline = cv2.getTextSize(text, font, font_scale, thickness)
            text_x = (width - text_width) // 2
            text_y = (height + text_height) // 2

            # Add text with outline for better visibility
            cv2.putText(
                frame, text, (text_x - 1, text_y - 1), font, font_scale, (0, 0, 0), thickness + 1
            )  # Black outline
            cv2.putText(frame, text, (text_x, text_y), font, font_scale, color, thickness)

            # Add smaller status text below
            status_text = f"Status: {status.title()}"
            font_scale_small = 0.5
            (status_width, status_height), _ = cv2.getTextSize(status_text, font, font_scale_small, 1)
            status_x = (width - status_width) // 2
            status_y = text_y + 40

            cv2.putText(
                frame, status_text, (status_x - 1, status_y - 1), font, font_scale_small, (0, 0, 0), 2
            )  # Black outline
            cv2.putText(
                frame, status_text, (status_x, status_y), font, font_scale_small, (200, 200, 200), 1
            )  # Light gray text

        except Exception as e:
            logger.warning(f"Could not add text overlay to status frame: {e}")

        return frame

    def _build_stream_captures(self):
        """Build simple OpenCV VideoCapture objects for each stream"""
        logger.info(f"🎬 Creating stream captures for {len(self.enabled_streams)} streams")
        print(f"🎬 Creating stream captures for {len(self.enabled_streams)} streams")

        for stream in self.enabled_streams:
            stream_id = stream["id"]
            stream_url = stream["url"]
            stream_name = stream["name"]

            try:
                # Simple direct capture - OpenCV will use FFmpeg backend automatically
                logger.info(f"📹 Opening stream {stream_name} (ID: {stream_id}): {stream_url}")
                print(f"📹 Opening stream {stream_name} (ID: {stream_id}): {stream_url}")

                # Set environment variable to control FFmpeg timeout
                import os  # noqa: PLC0415

                # Increase timeout to 60 seconds for IP cameras, use TCP transport
                os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = (
                    "rtsp_transport;tcp|timeout;60000000|buffer_size;1024000|max_delay;5000000"
                )

                # Explicitly use FFmpeg backend to avoid GStreamer warnings
                self.stream_caps[stream_id] = cv2.VideoCapture(stream_url, cv2.CAP_FFMPEG)

                # Set timeout and buffer properties before checking if opened
                self.stream_caps[stream_id].set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 60000)  # 60 second timeout
                self.stream_caps[stream_id].set(
                    cv2.CAP_PROP_READ_TIMEOUT_MSEC, 5000
                )  # 5 second read timeout (shorter for responsiveness)

                # Set some buffer properties to reduce latency but allow some buffering for stability
                if self.stream_caps[stream_id].isOpened():
                    # Set buffer size to 2-3 frames to handle network jitter while maintaining low latency
                    self.stream_caps[stream_id].set(cv2.CAP_PROP_BUFFERSIZE, 3)
                    # Set FPS to match expected camera FPS
                    self.stream_caps[stream_id].set(cv2.CAP_PROP_FPS, 30)
                    logger.info(f"✅ Stream {stream_id} opened successfully")
                    print(f"✅ Stream {stream_id} opened successfully")
                else:
                    logger.warning(f"⚠️ Stream {stream_id} failed to open immediately, will retry...")
                    print(f"⚠️ Stream {stream_id} failed to open immediately, will retry...")

                # Initialize stream status
                self.stream_status[stream_id] = "initializing"
                # Set timeout based on 4G mode
                is_4g_stream = os.getenv("4G_MODE", "false").lower() == "true"
                timeout_seconds = 60.0 if is_4g_stream else 30.0
                self.stream_init_timeout[stream_id] = time.time() + timeout_seconds

            except Exception as e:
                logger.error(f"❌ Failed to initialize stream {stream_id} ({stream_name}): {e}")
                self.stream_status[stream_id] = "error"

    async def recv(self):
        """Receive frames from individual streams, apply delays via frame skipping, and combine manually"""
        current_time = time.time()

        # Calculate relative timestamp for both video and vision (always needed)
        if self._start_time is None:
            self._start_time = current_time
        relative_timestamp = current_time - self._start_time

        # Initialize capture in background if not already done
        if not self.stream_caps:
            asyncio.create_task(self._initialize_capture())

        # Always return a frame - black/status frames if not ready, real video when ready
        # NEVER return None to prevent aiortc crashes

        # Calculate layout based on number of active streams (default to 2 if not initialized)
        num_streams = len(self.active_stream_ids) if self.active_stream_ids else 2
        if num_streams == 1:
            combined_width, combined_height = 720, 480
        elif num_streams == 2:
            combined_width, combined_height = 1440, 480
        else:
            combined_width, combined_height = 1440, 960

        # If no streams are ready, return black frame
        if not self.stream_caps or not any(cap.isOpened() for cap in self.stream_caps.values()):
            # Create simple black frame
            black_frame = np.zeros((combined_height, combined_width, 3), dtype=np.uint8)
            rgb_frame = cv2.cvtColor(black_frame, cv2.COLOR_BGR2RGB)
            rgb_frame = np.ascontiguousarray(rgb_frame, dtype=np.uint8)

            from av import VideoFrame  # noqa: PLC0415

            av_frame = VideoFrame.from_ndarray(rgb_frame, format="rgb24")

            pts = int(relative_timestamp * 90000)
            av_frame.pts = pts
            av_frame.time_base = Fraction(1, 90000)

            return av_frame

        try:
            current_time = time.time()

            # === CAPTURE FRESH FRAMES FROM EACH STREAM ===
            fresh_frames = {}
            for stream_id, cap in self.stream_caps.items():
                ret, frame = cap.read()
                if ret and frame is not None:
                    # Resize frame to 720x480 if needed
                    if frame.shape[:2] != (480, 720):
                        frame = cv2.resize(frame, (720, 480))

                    fresh_frames[stream_id] = frame
                    # Always update last_frames with fresh data
                    self.last_frames[stream_id] = frame
                    # Mark stream as ready on first successful frame
                    if self.stream_status[stream_id] == "initializing":
                        self.stream_status[stream_id] = "ready"
                        logger.info(f"✅ Stream {stream_id} is now ready")

                    # Track successful frame reads
                    self.frame_read_stats[stream_id]["success"] += 1
                else:
                    # Track failed frame reads
                    self.frame_read_stats[stream_id]["failures"] += 1
                    self.frame_read_stats[stream_id]["last_failure_time"] = current_time

                    # Check for timeout
                    if (
                        current_time > self.stream_init_timeout[stream_id]
                        and self.stream_status[stream_id] == "initializing"
                    ):
                        self.stream_status[stream_id] = "timeout"
                        logger.warning(f"⏰ Stream {stream_id} initialization timeout")
                    elif self.stream_status[stream_id] == "ready":
                        # Stream was working but stopped
                        self.stream_status[stream_id] = "error"
                        logger.warning(f"📡 Stream {stream_id} stopped receiving frames")
                        # Schedule reconnection attempt
                        asyncio.create_task(self._reconnect_stream(stream_id))

            # Report frame read statistics periodically to identify flickering causes
            self.frame_counter_for_stats += 1
            if self.frame_counter_for_stats % self.stats_report_interval == 0:
                for stream_id in self.active_stream_ids:
                    stats = self.frame_read_stats[stream_id]
                    total = stats["success"] + stats["failures"]
                    if total > 0:
                        (stats["success"] / total) * 100
                        failure_rate = (stats["failures"] / total) * 100
                        if failure_rate > 5.0:  # More than 5% failure rate
                            logger.warning(
                                f"⚠️ Stream {stream_id} has high failure rate ({failure_rate:.1f}%) - this could cause flickering!"
                            )
                # Reset stats for next interval
                for stream_id in self.active_stream_ids:
                    self.frame_read_stats[stream_id] = {
                        "success": 0,
                        "failures": 0,
                        "last_failure_time": self.frame_read_stats[stream_id]["last_failure_time"],
                    }

            # === APPLY TIME-SHIFT DELAY (SMOOTH DELAYED VIDEO) ===
            output_frames = {}
            for stream_id in self.active_stream_ids if self.active_stream_ids else []:
                delay_ms = self.stream_delays[stream_id]
                stream_status = self.stream_status[stream_id]

                # Check if stream is ready or if we need a status frame
                if stream_status in ["initializing", "timeout", "error"]:
                    # Generate status frame instead of waiting for real frame
                    status_frame = self._create_status_frame(720, 480, stream_id, stream_status)
                    output_frames[stream_id] = status_frame
                    continue

                # Add fresh frame to buffer with timestamp
                if stream_id in fresh_frames:
                    frame_with_time = StreamFrame(fresh_frames[stream_id], current_time, stream_id)
                    self.frame_buffers[stream_id].append(frame_with_time)

                    # Clean old frames (keep max 10 seconds)
                    while (
                        self.frame_buffers[stream_id]
                        and current_time - self.frame_buffers[stream_id][0].timestamp > 10.0
                    ):
                        self.frame_buffers[stream_id].popleft()

                if delay_ms == 0:
                    # No delay - use fresh frame or recent cached frame
                    if stream_id in fresh_frames:
                        output_frames[stream_id] = fresh_frames[stream_id]
                    elif self.last_frames[stream_id] is not None:
                        # Use most recent cached frame - add to buffer for anti-flickering
                        frame_with_time = StreamFrame(self.last_frames[stream_id], current_time, stream_id)
                        # Keep a small buffer of recent frames even with no delay to smooth over frame read failures
                        self.frame_buffers[stream_id].append(frame_with_time)
                        # Only keep last 2 seconds of frames for anti-flicker buffering
                        while (
                            self.frame_buffers[stream_id]
                            and current_time - self.frame_buffers[stream_id][0].timestamp > 2.0
                        ):
                            self.frame_buffers[stream_id].popleft()
                        output_frames[stream_id] = self.last_frames[stream_id]
                    else:
                        # Generate preparing frame if no data yet
                        output_frames[stream_id] = self._create_status_frame(720, 480, stream_id, "preparing")
                else:
                    # Time-shift delay - find frame closest to target delay time
                    delay_seconds = delay_ms / 1000.0
                    target_time = current_time - delay_seconds

                    best_frame = None
                    best_time_diff = float("inf")

                    # Find frame closest to target delay time (prevents drift during delay changes)
                    for buffered_frame in self.frame_buffers[stream_id]:
                        time_diff = abs(buffered_frame.timestamp - target_time)
                        if time_diff < best_time_diff:
                            best_time_diff = time_diff
                            best_frame = buffered_frame.frame

                    # Use best available frame or fallback to last frame
                    if best_frame is not None:
                        output_frames[stream_id] = best_frame
                    elif self.last_frames[stream_id] is not None:
                        output_frames[stream_id] = self.last_frames[stream_id]
                    else:
                        # Generate preparing frame if no data yet
                        output_frames[stream_id] = self._create_status_frame(720, 480, stream_id, "preparing")

            # === COMBINE FRAMES WITH DYNAMIC LAYOUT ===
            # Calculate layout based on number of active streams
            num_streams = len(self.active_stream_ids)
            if num_streams == 1:
                grid_cols, _grid_rows = 1, 1
                combined_width, combined_height = 720, 480
            elif num_streams == 2:
                grid_cols, _grid_rows = 2, 1
                combined_width, combined_height = 1440, 480
            elif num_streams in {3, 4}:
                grid_cols, _grid_rows = 2, 2
                combined_width, combined_height = 1440, 960
            else:
                grid_cols, _grid_rows = 2, 2  # Default
                combined_width, combined_height = 1440, 960

            # Create combined frame (dynamic size)
            combined_frame = np.zeros((combined_height, combined_width, 3), dtype=np.uint8)

            # If no frames at all, return black frame (startup case)
            if not output_frames:
                pass  # No frames available yet

            # Place frames in grid layout
            for i, stream_id in enumerate(self.active_stream_ids if self.active_stream_ids else []):
                if stream_id in output_frames:
                    # Calculate grid position
                    col = i % grid_cols
                    row = i // grid_cols

                    # Calculate position in combined frame
                    x_pos = col * 720
                    y_pos = row * 480

                    # Ensure we don't exceed frame bounds
                    if y_pos + 480 <= combined_height and x_pos + 720 <= combined_width:
                        combined_frame[y_pos : y_pos + 480, x_pos : x_pos + 720] = output_frames[stream_id]

            # Process vision (re-enabled for tracking) - detect what we're actually sending
            if vision_api and vision_api.is_tracking_enabled() and not self.vision_processing:
                # Process the exact combined frame that we're sending to WebRTC
                # Use current time - detections match what's displayed on screen
                asyncio.create_task(
                    self._process_frame_vision(
                        combined_frame.copy(), current_time, self.frame_count + 1, relative_timestamp
                    )
                )

            # Convert BGR to RGB for WebRTC
            rgb_frame = cv2.cvtColor(combined_frame, cv2.COLOR_BGR2RGB)
            rgb_frame = np.ascontiguousarray(rgb_frame, dtype=np.uint8)

            # Update FPS counter
            self.frame_count += 1
            now = time.time()
            if now - self.last_fps_time >= 1.0:
                self.measured_fps = self.frame_count / (now - self.last_fps_time)
                self.frame_count = 0
                self.last_fps_time = now

            # Create VideoFrame for aiortc
            from av import VideoFrame  # noqa: PLC0415

            av_frame = VideoFrame.from_ndarray(rgb_frame, format="rgb24")

            # Set proper timestamps for smooth playback
            # Use pts in 90kHz timebase (standard for video)
            pts = int(relative_timestamp * 90000)
            av_frame.pts = pts
            av_frame.time_base = Fraction(1, 90000)

            return av_frame

        except Exception as e:
            logger.error(f"Error in recv: {e}")
            # Return black frame on error
            black_frame = np.zeros((combined_height, combined_width, 3), dtype=np.uint8)
            rgb_frame = cv2.cvtColor(black_frame, cv2.COLOR_BGR2RGB)

            from av import VideoFrame  # noqa: PLC0415

            av_frame = VideoFrame.from_ndarray(rgb_frame, format="rgb24")
            av_frame.pts = int(relative_timestamp * 90000)
            av_frame.time_base = Fraction(1, 90000)
            return av_frame

    async def _initialize_capture(self):
        """Initialize the stream captures"""
        if self.stream_caps:
            return  # Already initialized

        try:
            logger.info("🔧 Initializing stream captures...")
            self._build_stream_captures()

            # Mark as running
            self.is_running = True

            # Count how many actually opened
            open_count = sum(1 for cap in self.stream_caps.values() if cap.isOpened())
            total_streams = len(self.stream_caps)

            if open_count > 0:
                logger.info(f"✅ {open_count}/{total_streams} stream captures opened successfully")
            else:
                logger.warning("⚠️ No streams opened immediately, will retry in background")

        except Exception as e:
            logger.error(f"Failed to initialize stream captures: {e}")

    async def _process_frame_vision(
        self, frame: np.ndarray, timestamp: float, frame_id: int, relative_timestamp: float
    ):
        """Multi-stream vision processing with synchronized timestamps"""
        if self.vision_processing:
            return  # Skip if already processing

        self.vision_processing = True
        try:
            # Process frame with vision API - pass stream information
            num_streams = len(self.active_stream_ids)
            stream_ids = list(self.active_stream_ids)

            if vision_api:
                result = vision_api.process_combined_frame(frame, timestamp, num_streams, stream_ids)
                if result:
                    if isinstance(result, VisionResult):
                        # Simple timestamp - just what we need
                        result.timestamp = timestamp
                        self.latest_vision_result = result

                else:
                    logger.warning(f"⚠️ Vision processing returned None for frame {frame_id}")
            else:
                logger.warning("Vision API not available for processing.")

        except Exception as e:
            logger.error(f"❌ Vision processing error for frame {frame_id}: {e}")
        finally:
            self.vision_processing = False

    async def _reconnect_stream(self, stream_id: int):
        """Attempt to reconnect a failed stream"""
        try:
            self.stream_status[stream_id] = "reconnecting"
            logger.info(f"🔄 Attempting to reconnect stream {stream_id}...")

            # Wait a bit before reconnecting (exponential backoff)
            await asyncio.sleep(5)

            # Close existing capture
            if stream_id in self.stream_caps:
                with contextlib.suppress(Exception):
                    self.stream_caps[stream_id].release()

            # Find stream configuration
            stream = next((s for s in self.enabled_streams if s["id"] == stream_id), None)
            if not stream:
                logger.error(f"Stream {stream_id} not found in configuration")
                return

            # Reconnect with simple OpenCV VideoCapture
            try:
                logger.info(f"🎬 Reconnecting stream {stream_id}...")

                # Set environment variable to control FFmpeg timeout
                import os  # noqa: PLC0415

                # Increase timeout to 60 seconds for IP cameras, use TCP transport
                os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = (
                    "rtsp_transport;tcp|timeout;60000000|buffer_size;1024000|max_delay;5000000"
                )

                # Explicitly use FFmpeg backend to avoid GStreamer warnings
                self.stream_caps[stream_id] = cv2.VideoCapture(stream["url"], cv2.CAP_FFMPEG)

                # Set timeout and buffer properties
                self.stream_caps[stream_id].set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 60000)
                self.stream_caps[stream_id].set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, 5000)

                # Set buffer size for stability
                if self.stream_caps[stream_id].isOpened():
                    self.stream_caps[stream_id].set(cv2.CAP_PROP_BUFFERSIZE, 3)
                    self.stream_caps[stream_id].set(cv2.CAP_PROP_FPS, 30)

                # Give it time to initialize
                await asyncio.sleep(3)

                # Check if reconnection successful
                if self.stream_caps[stream_id].isOpened():
                    self.stream_status[stream_id] = "initializing"
                    self.stream_init_timeout[stream_id] = time.time() + 60.0  # 60s timeout for reconnect
                    logger.info(f"✅ Stream {stream_id} reconnection successful - reinitializing...")
                else:
                    self.stream_status[stream_id] = "error"
                    logger.error(f"❌ Failed to reconnect stream {stream_id}")
                    # Try again later with longer delay
                    await asyncio.sleep(30)
                    if self.stream_status[stream_id] == "error":  # Still in error state
                        asyncio.create_task(self._reconnect_stream(stream_id))

            except Exception as e:
                logger.error(f"Error creating capture for stream {stream_id}: {e}")
                self.stream_status[stream_id] = "error"

        except Exception as e:
            logger.error(f"Error reconnecting stream {stream_id}: {e}")
            self.stream_status[stream_id] = "error"

    # Background vision processing removed - not needed and was causing conflicts

    def cleanup(self):
        """Cleanup resources and reset delays"""
        if self.stream_caps:
            for cap in self.stream_caps.values():
                cap.release()
            self.stream_caps = {}
            self.is_running = False

        # Reset all delays to 0 when stopping
        old_delays = self.stream_delays.copy()
        self.stream_delays = dict.fromkeys(self.active_stream_ids, 0)

        # Clear all frame buffers
        for stream_id in self.frame_buffers:
            self.frame_buffers[stream_id].clear()
        self.last_frames = dict.fromkeys(self.active_stream_ids)

        # Reset stream status
        self.stream_status = dict.fromkeys(self.active_stream_ids, "initializing")
        self.stream_init_timeout = {stream_id: time.time() + 30.0 for stream_id in self.active_stream_ids}

        if any(old_delays.values()):
            logger.info(f"🔄 Reset delays from {old_delays} to {self.stream_delays} (clean restart)")

        logger.info("🛑 Stream captures released and delays reset")

    async def set_stream_delay(self, stream_id: int, delay_ms: int) -> bool:
        """Set delay for a specific stream in milliseconds (INSTANT - no pipeline restart!)"""
        if stream_id not in self.active_stream_ids:
            logger.warning(f"Invalid stream_id: {stream_id} (active streams: {self.active_stream_ids})")
            return False

        # Store the delay setting
        old_delay = self.stream_delays[stream_id]
        self.stream_delays[stream_id] = delay_ms
        logger.info(f"🕐 Stream {stream_id} delay changing from {old_delay}ms to {delay_ms}ms")

        # Time-shift delay - smooth delayed video with immediate adjustment
        if delay_ms > 0:
            logger.info(
                f"✅ Time-shift delay updated instantly! Stream {stream_id} will jump to {delay_ms}ms delay (prevents drift)"
            )
        else:
            logger.info(f"✅ Delay cleared for stream {stream_id} - real-time video")

        # Clear old frames outside new delay range to prevent confusion
        if delay_ms > 0:
            max_age = (delay_ms / 1000.0) + 2.0  # Keep 2 extra seconds
            current_time = time.time()

            # Remove frames older than needed
            while self.frame_buffers[stream_id] and current_time - self.frame_buffers[stream_id][0].timestamp > max_age:
                self.frame_buffers[stream_id].popleft()

            logger.info(f"🔧 Optimized buffer for {delay_ms}ms delay - immediate sync adjustment")

        return True

    def get_stream_delays(self) -> dict:
        """Get current delay settings for all streams"""
        return self.stream_delays.copy()


class StreamCombinerManager:
    """Manages Stream Combiner - simplified from stream combiner version"""

    def __init__(self):
        self.track: StreamCombinerTrack | None = None
        self.is_running = False

    @property
    def vision_api(self):
        """Access the global vision API instance"""
        return vision_api

    async def start(self) -> bool:
        """Start the stream combiner (non-blocking)"""
        if self.is_running:
            logger.info("Stream combiner is already running")
            return True

        try:
            logger.info("🎬 Starting stream combiner in background...")

            # Get or create track (track is created immediately in get_video_track now)
            if not self.track:
                self.track = StreamCombinerTrack()

            # Start initialization in background
            asyncio.create_task(self._background_start())

            # Return immediately - WebRTC can start with black frames
            return True

        except Exception as e:
            logger.error(f"Error starting stream combiner: {e}")
            return False

    async def _background_start(self):
        """Background initialization of streams"""
        try:
            if not self.track:
                logger.error("No track available for background initialization")
                return

            logger.info("🔧 Initializing streams in background...")
            await self.track._initialize_capture()

            if self.track.is_running:
                self.is_running = True
                logger.info("✅ Stream combiner started successfully")
            else:
                logger.warning("⚠️ Stream combiner initialization incomplete")

        except Exception as e:
            logger.error(f"Error in background stream start: {e}")

    async def stop(self):
        """Stop the stream combiner"""
        if not self.is_running:
            return

        logger.info("🛑 Stopping stream combiner...")

        if self.track:
            self.track.cleanup()
            self.track = None

        self.is_running = False
        logger.info("✅ Stream combiner stopped")

    def get_video_track(self) -> StreamCombinerTrack | None:
        """Get the video track for WebRTC - always returns a track (black frames if not ready)"""
        if not self.track:
            # Create track immediately, even if streams aren't ready
            self.track = StreamCombinerTrack()
            logger.info("🎬 Created video track (will show black frames until streams are ready)")
        return self.track

    def is_alive(self) -> bool:
        """Check if the combiner is alive"""
        return (
            self.is_running
            and self.track is not None
            and bool(self.track.stream_caps)
            and all(cap.isOpened() for cap in self.track.stream_caps.values())
        )

    def get_stats(self) -> dict:
        """Get current stream statistics"""
        if self.track and self.is_running:
            return {
                "fps": round(self.track.measured_fps, 1),
                "frameCount": self.track.frame_count,
                "isRunning": True,
                "timestamp": time.time(),
            }
        return {"fps": 0, "frameCount": 0, "isRunning": False, "timestamp": time.time()}

    def get_latest_vision_result(self) -> Optional["VisionResult"]:
        """Get the latest vision processing result"""
        if self.track:
            return self.track.latest_vision_result
        return None

    def set_vision_api(self, api):
        """Set the VisionAPI instance to use"""
        global vision_api  # noqa: PLW0603
        vision_api = api
        logger.info(f"🔗 StreamCombinerManager received VisionAPI with {api.tracker.__class__.__name__}")

    def enable_vision_tracking(self):
        """Enable vision processing"""
        if vision_api:
            vision_api.enable_tracking()

            # Don't start background processing - let WebRTC handle vision processing
            # Background processing was causing conflicts with main vision pipeline
            logger.info("✅ Vision tracking enabled (WebRTC will handle processing)")

    def disable_vision_tracking(self):
        """Disable vision processing"""
        if vision_api:
            vision_api.disable_tracking()
            logger.info("🛑 Vision tracking disabled")

    def is_vision_tracking_enabled(self) -> bool:
        """Check if vision tracking is enabled"""
        return vision_api.is_tracking_enabled() if vision_api else False

    def get_vision_statistics(self) -> dict:
        """Get vision processing statistics"""
        return vision_api.get_statistics() if vision_api else {}

    def get_latest_frame(self) -> np.ndarray | None:
        """Get the latest frame from the combiner for calibration purposes"""
        if (
            not self.track
            or not self.track.stream_caps
            or not all(cap.isOpened() for cap in self.track.stream_caps.values())
        ):
            return None

        try:
            # Read current frame from each stream
            frames = []
            for stream_id, cap in self.track.stream_caps.items():
                ret, frame = cap.read()
                if ret and frame is not None:
                    # Resize frame to 720x480 if needed
                    if frame.shape[:2] != (480, 720):
                        frame = cv2.resize(frame, (720, 480))
                    frames.append((stream_id, frame))

            if frames:
                # Calculate layout based on number of active streams
                num_streams = len(self.track.active_stream_ids)
                if num_streams == 1:
                    grid_cols, _grid_rows = 1, 1
                    combined_width, combined_height = 720, 480
                elif num_streams == 2:
                    grid_cols, _grid_rows = 2, 1
                    combined_width, combined_height = 1440, 480
                elif num_streams in {3, 4}:
                    grid_cols, _grid_rows = 2, 2
                    combined_width, combined_height = 1440, 960
                else:
                    grid_cols, _grid_rows = 2, 2  # Default
                    combined_width, combined_height = 1440, 960

                # Combine frames manually with dynamic layout
                combined_frame = np.zeros((combined_height, combined_width, 3), dtype=np.uint8)
                for i, (_stream_id, frame) in enumerate(frames):
                    # Calculate grid position
                    col = i % grid_cols
                    row = i // grid_cols

                    # Calculate position in combined frame
                    x_pos = col * 720
                    y_pos = row * 480

                    # Ensure we don't exceed frame bounds
                    if y_pos + 480 <= combined_height and x_pos + 720 <= combined_width:
                        combined_frame[y_pos : y_pos + 480, x_pos : x_pos + 720] = frame

                return combined_frame
            logger.warning("No valid frames to combine")
            return None
        except Exception as e:
            logger.error(f"Error capturing frame: {e}")

        return None

    async def set_stream_delay(self, stream_id: int, delay_ms: int) -> bool:
        """Set delay for a specific stream"""
        if not self.track:
            logger.warning("No active track to set delay on")
            return False

        return await self.track.set_stream_delay(stream_id, delay_ms)

    def get_stream_delays(self) -> dict:
        """Get current delay settings for all streams"""
        if not self.track:
            try:
                enabled_streams = ServerConfig.get_enabled_streams()
                return {stream["id"]: 0 for stream in enabled_streams}
            except Exception as e:
                logger.warning(f"Could not get enabled streams: {e}")
                # Return default for 2 streams
                return {0: 0, 1: 0}
        return self.track.get_stream_delays()

    async def set_all_delays(self, delays: dict) -> bool:
        """Set delays for all streams at once"""
        if not self.track:
            logger.warning("No active track to set delays on")
            return False

        success = True
        for stream_id, delay_ms in delays.items():
            if not await self.set_stream_delay(stream_id, delay_ms):
                success = False
        return success


# Global manager instance
stream_combiner_manager = StreamCombinerManager()

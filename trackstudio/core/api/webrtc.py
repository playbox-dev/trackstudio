"""
WebRTC API with OpenCV Stream Combiner
Much simpler than the FFmpeg subprocess + RTSP approach!
"""

import asyncio
import json
import logging
from typing import Any

from aiortc import RTCConfiguration, RTCIceServer, RTCPeerConnection, RTCSessionDescription
from aiortc.exceptions import InvalidStateError
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ..config import ServerConfig
from ..stream_combiner import stream_combiner_manager

logger = logging.getLogger(__name__)
router = APIRouter()


class StreamConnection:
    """WebRTC connection using stream combiner"""

    def __init__(self, connection_id: str):
        self.connection_id = connection_id
        self.is_closed = False

        # Create RTCPeerConnection with STUN servers
        ice_servers = [RTCIceServer(url) for url in ServerConfig.STUN_SERVERS]
        config = RTCConfiguration(iceServers=ice_servers)
        self.pc = RTCPeerConnection(configuration=config)

        # Set up peer connection event handlers
        @self.pc.on("connectionstatechange")
        async def on_connectionstatechange():
            logger.info(f"🔗 RTCPeerConnection state changed to: {self.pc.connectionState} for {connection_id}")
            print(f"🔗 RTCPeerConnection state changed to: {self.pc.connectionState} for {connection_id}")

        @self.pc.on("iceconnectionstatechange")
        async def on_iceconnectionstatechange():
            logger.info(f"🧊 ICE connection state changed to: {self.pc.iceConnectionState} for {connection_id}")
            print(f"🧊 ICE connection state changed to: {self.pc.iceConnectionState} for {connection_id}")

        @self.pc.on("icegatheringstatechange")
        async def on_icegatheringstatechange():
            logger.info(f"🧊 ICE gathering state changed to: {self.pc.iceGatheringState} for {connection_id}")
            print(f"🧊 ICE gathering state changed to: {self.pc.iceGatheringState} for {connection_id}")

        @self.pc.on("signalingstatechange")
        async def on_signalingstatechange():
            logger.info(f"📶 Signaling state changed to: {self.pc.signalingState} for {connection_id}")
            print(f"📶 Signaling state changed to: {self.pc.signalingState} for {connection_id}")

        logger.info(f"Created WebRTC connection {connection_id}")

    async def create_answer(self, offer_sdp: str) -> str:
        """Create an answer for the received offer"""
        try:
            if self.is_closed:
                raise InvalidStateError("WebRTC connection is already closed")

            logger.info(f"🎯 Creating immediate WebRTC answer for {self.connection_id}")

            # Set remote description from offer first
            offer = RTCSessionDescription(sdp=offer_sdp, type="offer")
            await self.pc.setRemoteDescription(offer)
            logger.info(f"📥 Set remote description for {self.connection_id}")

            # Always get a video track immediately (black frames if stream combiner not ready)
            video_track = stream_combiner_manager.get_video_track()
            if not video_track:
                logger.warning("Stream combiner not ready, will start in background")
                # Start stream combiner in background (non-blocking)
                asyncio.create_task(stream_combiner_manager.start())
                # Get track anyway - it will provide black frames until ready
                video_track = stream_combiner_manager.get_video_track()

            if video_track:
                self.pc.addTrack(video_track)
                logger.info(f"📹 Added video track to connection {self.connection_id}")
            else:
                raise ValueError("Unable to get video track")

            # Create answer immediately
            logger.info(f"🔧 Creating WebRTC answer for {self.connection_id}...")
            answer = await self.pc.createAnswer()

            logger.info(f"🔧 Setting local description for {self.connection_id}...")
            await self.pc.setLocalDescription(answer)

            logger.info(f"✅ Created answer for stream combiner connection {self.connection_id}")
            logger.info(
                f"📊 States - PC: {self.pc.connectionState}, ICE: {self.pc.iceConnectionState}, Signaling: {self.pc.signalingState}"
            )

            return self.pc.localDescription.sdp

        except InvalidStateError as e:
            logger.error(f"Invalid state error for connection {self.connection_id}: {e}")
            self.is_closed = True
            raise ValueError(f"Connection state error: {e}") from e
        except Exception as e:
            logger.error(f"Failed to create answer for connection {self.connection_id}: {e}")
            self.is_closed = True
            raise

    async def close(self):
        """Close the WebRTC connection properly"""
        if self.is_closed:
            return

        self.is_closed = True

        try:
            logger.info(f"Closing stream combiner WebRTC connection {self.connection_id}")

            # Close peer connection with timeout
            try:
                await asyncio.wait_for(self.pc.close(), timeout=ServerConfig.WEBRTC_TIMEOUTS["close_timeout"])
                logger.info(f"Successfully closed RTCPeerConnection for {self.connection_id}")
            except asyncio.TimeoutError:
                logger.warning(
                    f"Timeout closing RTCPeerConnection for {self.connection_id} after {ServerConfig.WEBRTC_TIMEOUTS['close_timeout']}s"
                )
            except Exception as e:
                logger.warning(f"Error closing RTCPeerConnection for connection {self.connection_id}: {e}")

        except Exception as e:
            logger.error(f"Error during WebRTC connection cleanup for {self.connection_id}: {e}")

    def close_sync(self):
        """Synchronous close for emergency cleanup"""
        if self.is_closed:
            return

        self.is_closed = True
        logger.info(f"Emergency sync close for {self.connection_id}")

        # Schedule async close in background
        try:
            asyncio.create_task(self.close())
        except Exception as e:
            logger.warning(f"Error scheduling close for {self.connection_id}: {e}")

    # Note: Metadata transmission moved to dedicated WebSocket service


class StreamManager:
    """Manages stream combiner WebRTC connections"""

    def __init__(self):
        self.websockets: dict[str, WebSocket] = {}
        self.webrtc_connections: dict[str, StreamConnection] = {}

    async def connect_websocket(self, websocket: WebSocket, connection_id: str):
        """Accept a new WebSocket connection"""
        await websocket.accept()
        self.websockets[connection_id] = websocket
        logger.info(f"WebSocket connection {connection_id} established")

    async def disconnect(self, connection_id: str):
        """Remove a WebSocket connection and clean up WebRTC"""
        try:
            # Close WebRTC connection if it exists
            if connection_id in self.webrtc_connections:
                webrtc_conn = self.webrtc_connections[connection_id]
                await webrtc_conn.close()
                del self.webrtc_connections[connection_id]

            # Remove WebSocket
            if connection_id in self.websockets:
                del self.websockets[connection_id]
                logger.info(f"WebSocket connection {connection_id} closed")

        except Exception as e:
            logger.error(f"Error during disconnect cleanup for {connection_id}: {e}")

    async def send_message(self, connection_id: str, message: dict[str, Any]):
        """Send a message to a specific connection"""
        if connection_id in self.websockets:
            try:
                await self.websockets[connection_id].send_text(json.dumps(message))
            except Exception as e:
                logger.error(f"Error sending message to {connection_id}: {e}")
                asyncio.create_task(self.disconnect(connection_id))


# Global manager instance
manager = StreamManager()


@router.websocket("/webrtc")
async def websocket_endpoint(websocket: WebSocket, connection_id: str | None = None):
    """WebSocket endpoint for stream combiner WebRTC signaling"""
    if not connection_id:
        connection_id = f"stream_conn_{len(manager.websockets)}"

    try:
        await manager.connect_websocket(websocket, connection_id)

        # Send initial connection confirmation
        initial_message = {
            "type": "connection_established",
            "connection_id": connection_id,
            "message": "WebSocket connected successfully",
        }
        await manager.send_message(connection_id, initial_message)

        while True:
            try:
                # Receive message from client with longer timeout to avoid interference with stream init
                data = await asyncio.wait_for(
                    websocket.receive_text(), timeout=ServerConfig.WEBRTC_TIMEOUTS["connection_timeout"] + 60.0
                )
                message = json.loads(data)

                # Only log non-keepalive messages to reduce noise
                message_type = message.get("message_type") or message.get("type")
                if message_type not in ("ping", "pong"):
                    logger.info(f"Received message from {connection_id}: {message_type}")

                # Handle different message types
                if message_type == "offer":
                    await handle_stream_offer(connection_id, message)
                elif message_type in {"start-stream", "start-combined-stream"}:
                    await handle_start_stream(connection_id, message)
                elif message_type in {"stop-stream", "stop-combined-stream"}:
                    await handle_stop_stream(connection_id, message)
                elif message_type == "ping":
                    # Handle ping/keepalive - respond immediately without logging
                    await manager.send_message(connection_id, {"type": "pong"})
                elif message_type == "pong":
                    # Handle pong response silently
                    pass
                else:
                    logger.warning(f"Unknown message type: {message_type}")
                    await manager.send_message(
                        connection_id,
                        {"type": "error", "message": f"Unknown message type: {message_type}", "error_type": "protocol"},
                    )

            except asyncio.TimeoutError:  # noqa: PERF203
                # Send keepalive ping less frequently to avoid interference
                logger.debug(f"Sending keepalive ping to {connection_id}")
                await manager.send_message(connection_id, {"type": "ping"})

            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON from {connection_id}: {e}")
                await manager.send_message(
                    connection_id, {"type": "error", "message": "Invalid JSON format", "error_type": "protocol"}
                )
            except Exception as e:
                logger.error(f"Error processing message from {connection_id}: {e}")
                break

    except WebSocketDisconnect:
        logger.info(f"WebSocket {connection_id} disconnected normally")
    except Exception as e:
        logger.error(f"WebSocket error for {connection_id}: {e}")
    finally:
        await manager.disconnect(connection_id)


async def handle_stream_offer(connection_id: str, message: dict[str, Any]):
    """Handle WebRTC offer for stream combiner"""
    try:
        offer_sdp = message.get("sdp")

        if not offer_sdp:
            await manager.send_message(
                connection_id,
                {"type": "error", "message": "Missing SDP in offer", "error_type": "protocol", "retryable": False},
            )
            return

        logger.info(f"🎯 Processing stream combiner offer from {connection_id}")

        # Check vision tracking status
        stream_combiner_manager.is_vision_tracking_enabled()

        # Clean up any existing connection for this connection_id
        if connection_id in manager.webrtc_connections:
            old_conn = manager.webrtc_connections[connection_id]
            await old_conn.close()
            del manager.webrtc_connections[connection_id]

        # Create WebRTC connection with stream combiner
        webrtc_conn = StreamConnection(connection_id)
        manager.webrtc_connections[connection_id] = webrtc_conn

        # Create answer with timeout
        try:
            answer_sdp = await asyncio.wait_for(
                webrtc_conn.create_answer(offer_sdp), timeout=ServerConfig.WEBRTC_TIMEOUTS["answer_timeout"]
            )
        except asyncio.TimeoutError as e:
            raise Exception(
                f"Timeout creating WebRTC answer after {ServerConfig.WEBRTC_TIMEOUTS['answer_timeout']}s"
            ) from e

        # Send answer back to client
        response = {"type": "answer", "sdp": answer_sdp}

        await manager.send_message(connection_id, response)
        logger.info(f"Sent stream combiner answer to {connection_id}")

    except ValueError as e:
        logger.error(f"Configuration error for stream combiner: {e}")
        await manager.send_message(
            connection_id, {"type": "error", "message": str(e), "error_type": "configuration", "retryable": True}
        )
    except Exception as e:
        logger.error(f"Error handling stream combiner offer from {connection_id}: {e}")

        await manager.send_message(
            connection_id,
            {
                "type": "error",
                "message": f"Failed to process offer: {str(e)}",
                "error_type": "unknown",
                "retryable": True,
            },
        )

        # Clean up failed connection
        if connection_id in manager.webrtc_connections:
            await manager.webrtc_connections[connection_id].close()
            del manager.webrtc_connections[connection_id]


async def handle_start_stream(connection_id: str, _message: dict[str, Any]):
    """Handle start stream request"""
    logger.info(f"Starting stream for connection {connection_id}")

    response = {"type": "stream-started", "status": "success"}
    await manager.send_message(connection_id, response)


async def handle_stop_stream(connection_id: str, _message: dict[str, Any]):
    """Handle stop stream request"""
    logger.info(f"Stopping stream for connection {connection_id}")

    # Clean up WebRTC connection
    if connection_id in manager.webrtc_connections:
        await manager.webrtc_connections[connection_id].close()
        del manager.webrtc_connections[connection_id]

    response = {"type": "stream-stopped", "status": "success"}
    await manager.send_message(connection_id, response)


@router.get("/stream-stats")
async def get_stream_stats():
    """Get current combined stream statistics"""
    try:
        stats = stream_combiner_manager.get_stats()
        return {"status": "success", "data": stats}
    except Exception as e:
        logger.error(f"Error getting stream stats: {e}")
        return {
            "status": "error",
            "message": str(e),
            "data": {"fps": 0, "frameCount": 0, "isRunning": False, "timestamp": 0},
        }

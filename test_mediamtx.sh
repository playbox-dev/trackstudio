#!/bin/bash

echo "🚀 Starting MediaMTX Test Setup for TrackStudio"
echo "==============================================="
echo ""

# Function to cleanup on exit
cleanup() {
    echo ""
    echo "🛑 Stopping all processes..."
    docker compose down
    pkill -f "tests/stream_camera[0-1]_ffmpeg.sh"
    exit 0
}

# Set trap for cleanup
trap cleanup EXIT INT TERM

# Check if docker compose is available
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install Docker first."
    exit 1
fi

# Start MediaMTX
echo "📡 Starting MediaMTX server..."
docker compose up -d mediamtx

# Wait for MediaMTX to start
echo "⏳ Waiting for MediaMTX to start..."
sleep 5

echo "✅ MediaMTX is running!"
echo ""
echo "📺 MediaMTX endpoints:"
echo "   RTSP: rtsp://localhost:8554/"
echo "   RTMP: rtmp://localhost:1935/"
echo "   HLS:  http://localhost:8888/"
echo "   WebRTC: http://localhost:8889/"
echo ""

# Start test streams
echo "🎬 Starting test streams..."
echo ""

# Make scripts executable
chmod +x tests/stream_camera0_ffmpeg.sh tests/stream_camera1_ffmpeg.sh

# Start camera streams in background
./tests/stream_camera0_ffmpeg.sh &
sleep 2
./tests/stream_camera1_ffmpeg.sh &

echo ""
echo "✅ Test streams are starting..."
echo ""
echo "📹 Available RTSP streams for TrackStudio:"
echo "   Camera 0: rtsp://localhost:8554/camera0"
echo "   Camera 1: rtsp://localhost:8554/camera1"
echo ""
echo "🎯 To use with TrackStudio:"
echo "   uv run trackstudio run -c config_test.json"
echo ""
echo "📊 To monitor MediaMTX:"
echo "   docker compose logs -f mediamtx"
echo ""
echo "Press Ctrl+C to stop all services..."

# Keep script running
while true; do
    sleep 1
done

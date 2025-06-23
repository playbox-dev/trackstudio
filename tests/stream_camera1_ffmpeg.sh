#!/bin/bash

# Get server IP from environment variable, default to localhost
SERVER_IP=${SERVER_IP:-localhost}

# Video file to stream (change this to your video file)
VIDEO_FILE="tests/videos/cam2.mp4"

echo "🎬 Starting Camera 1 stream with FFmpeg to MediaMTX"
echo "   Source: $VIDEO_FILE"
echo "   Publishing to: rtmp://${SERVER_IP}:1935/camera1"
echo "   Resolution: 720x480 @ 15fps"
echo ""
echo "   Stream will be available at:"
echo "   📹 RTSP: rtsp://${SERVER_IP}:8554/camera1"
echo "   🌐 RTMP: rtmp://${SERVER_IP}:1935/camera1"
echo "   🎥 HLS:  http://${SERVER_IP}:8888/camera1"
echo ""
echo "   Press Ctrl+C to stop"

# Check if video file exists, use test pattern if not
if [ ! -f "$VIDEO_FILE" ]; then
    echo "⚠️  Video file not found: $VIDEO_FILE"
    echo "   Using test pattern instead..."

    # Generate test pattern with overlay (different color for camera 1)
    while true; do
        ffmpeg -f lavfi -i testsrc2=size=720x480:rate=15 \
            -vf "hue=h=90:s=1,
                 drawtext=text='Camera 1 - Test Pattern':x=10:y=10:fontsize=24:fontcolor=white:box=1:boxcolor=black@0.5,
                 drawtext=text='%{localtime}':x=10:y=40:fontsize=20:fontcolor=white:box=1:boxcolor=black@0.5" \
            -c:v libx264 \
            -preset ultrafast \
            -tune zerolatency \
            -g 30 \
            -b:v 2048k \
            -f flv \
            rtmp://${SERVER_IP}:1935/camera1

        echo "Stream disconnected, restarting in 2 seconds..."
        sleep 2
    done
else
    # Stream video file
    while true; do
        ffmpeg -re -stream_loop -1 -i "$VIDEO_FILE" \
            -vf "drawtext=text='Camera 1':x=10:y=10:fontsize=24:fontcolor=white:box=1:boxcolor=black@0.5" \
            -c:v libx264 \
            -preset ultrafast \
            -tune zerolatency \
            -s 720x480 \
            -r 15 \
            -g 30 \
            -b:v 2048k \
            -f flv \
            rtmp://${SERVER_IP}:1935/camera1

        echo "Stream disconnected, restarting in 2 seconds..."
        sleep 2
    done
fi

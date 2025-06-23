import React, { useRef, useEffect } from 'react'
import type { VisionMetadata } from '../services/VisionWebSocket'
import { useTimestampSync } from '../hooks/useTimestampSync'
import { useAppSelector } from '../store/hooks'
import { selectIndividualResolution, selectDisplayScale } from '../store/slices/cameraConfigSlice'

interface MultiStreamVisionOverlayProps {
  videoRef: React.RefObject<HTMLVideoElement | null>
  visionData: VisionMetadata | null
  className?: string
}

const COLORS = [
  '#ff6b6b', '#4ecdc4', '#45b7d1', '#f9ca24', '#f0932b',
  '#eb4d4b', '#6c5ce7', '#a29bfe', '#fd79a8', '#fdcb6e'
]

export const MultiStreamVisionOverlay: React.FC<MultiStreamVisionOverlayProps> = ({
  videoRef,
  visionData,
  className = ''
}) => {
  const canvasRef = useRef<HTMLCanvasElement>(null)

  // Get camera resolution and display scale from Redux store
  const individualResolution = useAppSelector(selectIndividualResolution)
  const displayScale = useAppSelector(selectDisplayScale)
  const DETECTION_CAMERA_WIDTH = individualResolution.width
  const DETECTION_CAMERA_HEIGHT = individualResolution.height

  // Use timestamp synchronization hook to handle WebRTC latency
  const { syncedData, syncStatus } = useTimestampSync(videoRef, visionData)

  // Simple hash function for track colors
  const getTrackColor = (trackId: string): string => {
    let hash = 0
    for (let i = 0; i < trackId.length; i++) {
      hash = (hash * 31 + trackId.charCodeAt(i)) % COLORS.length
    }
    return COLORS[Math.abs(hash)]
  }

  // Calculate grid layout based on number of streams
  const getGridLayout = (numStreams: number) => {
    if (numStreams === 1) {
      return { cols: 1, rows: 1 }
    } else if (numStreams === 2) {
      return { cols: 2, rows: 1 }
    } else if (numStreams <= 4) {
      return { cols: 2, rows: 2 }
    } else {
      return { cols: 2, rows: 2 } // Default
    }
  }

  // Get stream position in grid
  const getStreamPosition = (streamIndex: number, gridCols: number) => {
    const col = streamIndex % gridCols
    const row = Math.floor(streamIndex / gridCols)
    return { col, row }
  }

  // Draw overlay function for all streams
  const drawOverlay = () => {
    const canvas = canvasRef.current
    const video = videoRef.current

    if (!canvas || !video) return

    const ctx = canvas.getContext('2d')
    if (!ctx) return

    const rect = video.getBoundingClientRect()

    // Position canvas exactly over video element
    const videoParent = video.offsetParent || document.body
    const parentRect = videoParent.getBoundingClientRect()

    // Calculate video position relative to its offset parent
    const videoRelativeLeft = rect.left - parentRect.left
    const videoRelativeTop = rect.top - parentRect.top

    // Position and size canvas to match video exactly
    canvas.style.left = `${videoRelativeLeft}px`
    canvas.style.top = `${videoRelativeTop}px`
    canvas.style.width = `${rect.width}px`
    canvas.style.height = `${rect.height}px`
    canvas.width = rect.width
    canvas.height = rect.height



    // Clear canvas
    ctx.clearRect(0, 0, canvas.width, canvas.height)

    // Use synchronized data if available, fallback to latest vision data
    const dataToRender = syncedData?.visionData || visionData

    if (!dataToRender) {
      // Clear canvas and show waiting message
      ctx.clearRect(0, 0, canvas.width, canvas.height)
      ctx.fillStyle = '#ffffff'
      ctx.font = '12px Arial'
      ctx.fillText('Waiting for vision data...', 10, 20)
      ctx.fillText(`Sync: ${syncStatus.matchesFound} matches, ${syncStatus.videoFrames}v/${syncStatus.visionData}d`, 10, 35)
      return
    }

    // Get number of active streams and layout
    const numStreams = dataToRender.num_streams || 2
    const activeStreamIds = dataToRender.active_stream_ids || [0, 1]
    const { cols: gridCols, rows: gridRows } = getGridLayout(numStreams)

    // Calculate where the actual video content sits within the CSS-scaled video element
    const backendWidth = individualResolution.width * gridCols
    const backendHeight = individualResolution.height * gridRows
    const videoAspectRatio = backendWidth / backendHeight

    // The video element's CSS dimensions (from getBoundingClientRect)
    const elementWidth = rect.width
    const elementHeight = rect.height
    const elementAspectRatio = elementWidth / elementHeight

    // Calculate where the video content actually appears within the CSS element
    let videoContentWidth: number
    let videoContentHeight: number
    let videoOffsetX: number = 0
    let videoOffsetY: number = 0

    // For object-fit: contain, video is scaled to fit within element while maintaining aspect ratio
    if (videoAspectRatio > elementAspectRatio) {
      // Video is wider than element - letterboxed top/bottom (black bars above/below)
      videoContentWidth = elementWidth
      videoContentHeight = elementWidth / videoAspectRatio
      videoOffsetX = 0
      videoOffsetY = (elementHeight - videoContentHeight) / 2
    } else {
      // Video is taller than element - pillarboxed left/right (black bars left/right)
      videoContentWidth = elementHeight * videoAspectRatio
      videoContentHeight = elementHeight
      videoOffsetX = (elementWidth - videoContentWidth) / 2
      videoOffsetY = 0
    }

    // No scaling correction needed - letterboxing/pillarboxing handles positioning correctly

    // Calculate stream dimensions in the combined frame
    const streamWidth = videoContentWidth / gridCols
    const streamHeight = videoContentHeight / gridRows

    // Scale factors from detection space to display space
    // Note: streamWidth/streamHeight already include the display scale factor
    // because they're calculated from the video element's actual displayed dimensions
    const scaleX = (streamWidth / DETECTION_CAMERA_WIDTH)
    const scaleY = (streamHeight / DETECTION_CAMERA_HEIGHT)





    // Process each active stream
    activeStreamIds.forEach((streamId: number, index: number) => {
      // Get stream position in grid
      const { col, row } = getStreamPosition(index, gridCols)

      // Calculate stream position in the combined frame
      const streamOffsetX = videoOffsetX + (col * streamWidth)
      const streamOffsetY = videoOffsetY + (row * streamHeight)

      // Get stream data from new all_streams format
      let streamData = null
      if (dataToRender.all_streams && dataToRender.all_streams[streamId.toString()]) {
        streamData = dataToRender.all_streams[streamId.toString()]
      }



      if (!streamData) {
        // Draw placeholder for missing stream
        ctx.strokeStyle = '#666666'
        ctx.lineWidth = 2
        ctx.strokeRect(streamOffsetX, streamOffsetY, streamWidth, streamHeight)
        ctx.fillStyle = '#666666'
        ctx.font = '14px Arial'
        ctx.fillText(`Stream ${streamId}: No Data`, streamOffsetX + 10, streamOffsetY + 30)
        return
      }

      // Draw stream border for debugging
      ctx.strokeStyle = '#333333'
      ctx.lineWidth = 1
      ctx.strokeRect(streamOffsetX, streamOffsetY, streamWidth, streamHeight)

      // Draw detections (red bounding boxes) - these show RF-DETR is working
      ctx.strokeStyle = '#ff0000'
      ctx.lineWidth = 3
      ctx.font = '12px Arial'

      streamData.detections.forEach((detection: any, detIndex: number) => {
        const [x, y, w, h] = detection.bbox

        // Transform from detection space to display space
        const scaledX = x * scaleX + streamOffsetX
        const scaledY = y * scaleY + streamOffsetY
        const scaledW = w * scaleX
        const scaledH = h * scaleY

        // Draw bounding box with detection indicator
        ctx.strokeRect(scaledX, scaledY, scaledW, scaledH)

        // Draw "D" indicator for detection
        ctx.fillStyle = '#ff0000'
        ctx.beginPath()
        ctx.arc(scaledX + 8, scaledY + 8, 6, 0, 2 * Math.PI)
        ctx.fill()
        ctx.fillStyle = '#ffffff'
        ctx.font = 'bold 10px Arial'
        ctx.fillText('D', scaledX + 5, scaledY + 12)
        ctx.font = '12px Arial'

        // Draw label with confidence
        const label = `${detection.class_name} ${(detection.confidence * 100).toFixed(0)}%`
        const textMetrics = ctx.measureText(label)
        const textHeight = 16

        // Background for text
        ctx.fillStyle = 'rgba(255, 0, 0, 0.8)'
        ctx.fillRect(scaledX, scaledY - textHeight, textMetrics.width + 8, textHeight)

        // Text
        ctx.fillStyle = '#ffffff'
        ctx.fillText(label, scaledX + 4, scaledY - 4)

        // Draw center point
        ctx.fillStyle = '#00ff00'
        ctx.beginPath()
        ctx.arc(scaledX + scaledW/2, scaledY + scaledH/2, 3, 0, 2 * Math.PI)
        ctx.fill()
      })

      // Draw tracks (colored bounding boxes)
      streamData.tracks.forEach((track: any) => {
        const [x, y, w, h] = track.bbox

        // Transform from detection space to display space
        const scaledX = x * scaleX + streamOffsetX
        const scaledY = y * scaleY + streamOffsetY
        const scaledW = w * scaleX
        const scaledH = h * scaleY

        const color = getTrackColor(track.id)

        // Draw track bounding box
        ctx.strokeStyle = color
        ctx.lineWidth = 4
        ctx.strokeRect(scaledX, scaledY, scaledW, scaledH)

        // Draw track center point
        const centerX = scaledX + scaledW / 2
        const centerY = scaledY + scaledH / 2

        ctx.fillStyle = color
        ctx.beginPath()
        ctx.arc(centerX, centerY, 5, 0, 2 * Math.PI)
        ctx.fill()

        // Draw "T" indicator for track
        ctx.fillStyle = color
        ctx.beginPath()
        ctx.arc(scaledX + 8, scaledY + 8, 6, 0, 2 * Math.PI)
        ctx.fill()
        ctx.fillStyle = '#ffffff'
        ctx.font = 'bold 10px Arial'
        ctx.fillText('T', scaledX + 5, scaledY + 12)

        // Draw track ID
        const trackLabel = `ID: ${track.id}`
        const textMetrics = ctx.measureText(trackLabel)
        const textHeight = 16

        // Background for text
        ctx.fillStyle = color
        ctx.fillRect(scaledX, scaledY + scaledH + 2, textMetrics.width + 8, textHeight)

        // Text
        ctx.fillStyle = '#ffffff'
        ctx.font = 'bold 12px Arial'
        ctx.fillText(trackLabel, scaledX + 4, scaledY + scaledH + textHeight - 2)
        ctx.font = '12px Arial'
      })

      // Draw stream info overlay
      ctx.fillStyle = 'rgba(0, 0, 0, 0.7)'
      ctx.fillRect(streamOffsetX + 5, streamOffsetY + 5, 120, 30)
      ctx.fillStyle = '#ffffff'
      ctx.font = 'bold 11px Arial'
      ctx.fillText(`Stream ${streamId}`, streamOffsetX + 10, streamOffsetY + 20)
      ctx.font = '10px Arial'
      ctx.fillText(
        `${streamData.detections.length} det, ${streamData.tracks.length} tracks`,
        streamOffsetX + 10,
        streamOffsetY + 32
      )
    })

    // Draw overall summary and detailed debug info
    const totalDetections = Object.values(dataToRender.all_streams || {})
      .reduce((sum: number, stream: any) => sum + stream.detections.length, 0)
    const totalTracks = Object.values(dataToRender.all_streams || {})
      .reduce((sum: number, stream: any) => sum + stream.tracks.length, 0)

    // Draw summary background
    const summaryHeight = 45
    ctx.fillStyle = 'rgba(0, 0, 0, 0.8)'
    ctx.fillRect(0, canvas.height - summaryHeight, canvas.width, summaryHeight)

    // Main summary line
    ctx.fillStyle = '#ffffff'
    ctx.font = 'bold 12px Arial'
    ctx.fillText(
      `🔴 ${totalDetections} RF-DETR Detections | 🌈 ${totalTracks} DeepSORT Tracks | 🗺️ ${dataToRender.bev_tracks.length} BEV | Frame ${dataToRender.frame_id}`,
      10,
      canvas.height - 30
    )

    // Per-stream breakdown
    ctx.font = '10px Arial'
    ctx.fillStyle = '#cccccc'
    const streamBreakdown = activeStreamIds.map((streamId: number) => {
      const streamData = dataToRender.all_streams?.[streamId.toString()]
      const detCount = streamData?.detections.length || 0
      const trackCount = streamData?.tracks.length || 0
      return `Cam${streamId}: ${detCount}d/${trackCount}t`
    }).join(' | ')

    ctx.fillText(
      `${streamBreakdown} | ${syncedData ? '✅ SYNCED' : '⚠️ LATEST'} | Processing: ${dataToRender.processing_time_ms?.toFixed(1)}ms`,
      10,
      canvas.height - 15
    )

    // Draw legend in top-right corner
    const legendWidth = 200
    const legendHeight = 80  // Increased height for sync status
    const legendX = canvas.width - legendWidth - 10
    const legendY = 10

    ctx.fillStyle = 'rgba(0, 0, 0, 0.8)'
    ctx.fillRect(legendX, legendY, legendWidth, legendHeight)

    ctx.font = 'bold 11px Arial'
    ctx.fillStyle = '#ffffff'
    ctx.fillText('🔍 Debug Legend:', legendX + 5, legendY + 15)

    ctx.font = '10px Arial'
    ctx.fillStyle = '#ff0000'
    ctx.fillText('🔴 D = RF-DETR Detection', legendX + 5, legendY + 30)

    ctx.fillStyle = '#00ff00'
    ctx.fillText('🌈 T = DeepSORT Track', legendX + 5, legendY + 45)

    // Health indicator
    const healthText = totalDetections > 0 ?
      (totalTracks > 0 ? '✅ Both Working' : '⚠️ Tracking Issues') :
      '❌ Detection Issues'
    ctx.fillStyle = totalDetections > 0 && totalTracks > 0 ? '#00ff00' : '#ff6666'
    ctx.fillText(healthText, legendX + 105, legendY + 37)

    // SYNC STATUS - More visible
    ctx.font = 'bold 12px Arial'
    ctx.fillStyle = syncedData ? '#00ff00' : '#ffaa00'
    ctx.fillText(syncedData ? '✅ SYNCED' : '⚠️ FALLBACK', legendX + 5, legendY + 65)
  }

  // Update overlay when data changes
  useEffect(() => {
    drawOverlay()
  }, [syncedData, visionData, videoRef, displayScale])



  // Handle video resize
  useEffect(() => {
    const video = videoRef.current
    if (!video) return

    const resizeObserver = new ResizeObserver(drawOverlay)
    resizeObserver.observe(video)

    return () => {
      resizeObserver.disconnect()
    }
  }, [])

  // Clear canvas when component unmounts (when tracking stops)
  useEffect(() => {
    return () => {
      const canvas = canvasRef.current
      if (canvas) {
        const ctx = canvas.getContext('2d')
        if (ctx) {
          ctx.clearRect(0, 0, canvas.width, canvas.height)
        }
      }
    }
  }, [])

  // Clear canvas immediately when vision data becomes null
  useEffect(() => {
    if (!visionData) {
      const canvas = canvasRef.current
      if (canvas) {
        const ctx = canvas.getContext('2d')
        if (ctx) {
          ctx.clearRect(0, 0, canvas.width, canvas.height)
          // Show "Vision Tracking Stopped" message
          ctx.fillStyle = '#ff6666'
          ctx.font = 'bold 14px Arial'
          ctx.fillText('Vision Tracking Stopped', 10, 25)
        }
      }
    }
  }, [visionData])

  return (
    <canvas
      ref={canvasRef}
      className={`absolute top-0 left-0 pointer-events-none ${className}`}
      style={{ zIndex: 10 }}
    />
  )
}

export default MultiStreamVisionOverlay

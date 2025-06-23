import { useRef, useEffect, useState } from 'react'
import type { Camera, CombinedStreamState, StreamError, BEVTrack } from '../types'
import type { VisionWebSocketService, VisionMetadata } from '../services/VisionWebSocket'
import MultiStreamVisionOverlay from './MultiStreamVisionOverlay'
import { useAppDispatch, useAppSelector } from '../store/hooks'
import { setVisionEnabled, setVisionLoading } from '../store/slices/visionSlice'
import { selectCombinedResolution, selectIndividualResolution, selectScaledCombinedResolution } from '../store/slices/cameraConfigSlice'
import { setStreamDelays } from '../store/slices/streamSlice'
import { selectShowAllCameras } from '../store/slices/uiSlice'
import { StreamDelayControls } from './StreamDelayControls'
import VisionProcessorControls from './VisionProcessorControls'
import {
  getCameraColorVariants,
  getTrackColorVariants,
  getTrajectoryColors,
  SYSTEM_COLORS
} from '../utils/colors'
import { FaEye, FaEyeSlash, FaCrosshairs, FaHourglassHalf, FaRoute, FaChevronDown } from 'react-icons/fa'
import { StreamErrorOverlay, StreamLoadingOverlay } from './shared'

interface CombinedViewTabProps {
  cameras: Camera[]
  combinedStreamState: CombinedStreamState
  combinedStreamError?: StreamError
  onCombinedStreamToggle: () => Promise<void>
  onRetryCombinedStream: () => Promise<void>
  visionMetadata: VisionMetadata | null
  visionWebSocket: VisionWebSocketService
  visionWebSocketConnected: boolean
}

export function CombinedViewTab({
  cameras,
  combinedStreamState,
  combinedStreamError,
  onCombinedStreamToggle,
  onRetryCombinedStream,
  visionMetadata,
  visionWebSocket,
}: CombinedViewTabProps) {
  const dispatch = useAppDispatch()
  const videoRef = useRef<HTMLVideoElement>(null)
  const bevCanvasRef = useRef<HTMLCanvasElement>(null)
  const [selectedTrack, setSelectedTrack] = useState<string | null>(null)
  const [visionControlsVisible, setVisionControlsVisible] = useState(true)
  const [calibrationData, setCalibrationData] = useState<any>(null)

  // Redux state selectors
  const isVisionEnabled = useAppSelector(state => state.vision.isEnabled)
  const visionLoading = useAppSelector(state => state.vision.isLoading)
  const visionWebSocketConnected = useAppSelector(state => state.vision.webSocketConnected)
  const combinedResolution = useAppSelector(selectCombinedResolution)
  const individualResolution = useAppSelector(selectIndividualResolution)
  const scaledCombinedResolution = useAppSelector(selectScaledCombinedResolution)
  const showAllCameras = useAppSelector(selectShowAllCameras)

  const baseButtonClass = "mt-4 px-6 py-3 rounded text-sm font-medium transition-colors min-w-[180px]"

  // Helper function to get the display ID for a track
  const getTrackDisplayId = (visionTrack: any): string => {
    if (visionTrack.global_id !== undefined && visionTrack.global_id !== null) {
      return `global_${visionTrack.global_id}`
    }
    return visionTrack.id
  }

  // Transform vision tracks to BEV format
  const tracks: BEVTrack[] = visionMetadata?.bev_tracks.map((visionTrack, index) => {
    console.log(`🔍 COMBINED VIEW - BEV TRACK ${index} - DIRECT PIXELS:`, {
      track_id: getTrackDisplayId(visionTrack),
      backend_pixels: visionTrack.position,
      using_directly: {
        bev_x: visionTrack.position[0],
        bev_y: visionTrack.position[1]
      }
    })

    return {
      track_id: getTrackDisplayId(visionTrack),
      // Backend outputs pixels directly in 600x600 space, same as calibration after scaling
      bev_x: visionTrack.position[0],
      bev_y: visionTrack.position[1],
      confidence: visionTrack.confidence,
      global_id: visionTrack.global_id,
      trajectory: visionTrack.trajectory // Preserve trajectory data
    }
  }) || []

  // Debug log when tracks have trajectory data
  useEffect(() => {
    if (tracks.length > 0) {
      const tracksWithTrajectory = tracks.filter(t => t.trajectory && t.trajectory.length > 1)
      if (tracksWithTrajectory.length > 0) {
        console.log('🛤️ Found tracks with trajectory:', tracksWithTrajectory.map(t => ({
          id: t.track_id,
          trajectoryLength: t.trajectory?.length || 0
        })))
      }
    }
  }, [tracks])

  // Fetch initial stream delays on mount
  useEffect(() => {
    const fetchDelays = async () => {
      try {
        const response = await fetch('/api/cameras/stream-delays')
        if (response.ok) {
          const data = await response.json()
          dispatch(setStreamDelays(data.delays))
        }
      } catch (error) {
        console.error('Failed to fetch stream delays:', error)
      }
    }
    fetchDelays()
  }, [dispatch])

  // Fetch calibration data for reference points
  useEffect(() => {
    const fetchCalibrationData = async () => {
      try {
        const response = await fetch('/api/calibration/calibration-data')
        if (response.ok) {
          const data = await response.json()
          if (data.success) {
            setCalibrationData(data.calibration_data)
          }
        }
      } catch (error) {
        console.error('Failed to load calibration data:', error)
      }
    }
    fetchCalibrationData()
  }, [])

  // Function to draw calibration reference points
  const drawCalibrationPoints = (ctx: CanvasRenderingContext2D) => {
    if (!calibrationData) return

    Object.entries(calibrationData).forEach(([cameraKey, cameraData]: [string, any]) => {
      const cameraId = parseInt(cameraKey.replace('camera', ''))
      const bevPoints = cameraData.bev_points

      if (bevPoints && Array.isArray(bevPoints)) {
        bevPoints.forEach((point: [number, number], index: number) => {
          // Convert normalized coordinates [0-1] to canvas coordinates
          const x = point[0] * 600 // Canvas width
          const y = point[1] * 600 // Canvas height

          // Draw reference point with camera-specific styling
          const cameraColors = getCameraColorVariants(cameraId)
          ctx.fillStyle = cameraColors.bright
          ctx.strokeStyle = SYSTEM_COLORS.border
          ctx.lineWidth = 2

          // Draw diamond shape for reference points
          ctx.beginPath()
          ctx.moveTo(x, y - 6)
          ctx.lineTo(x + 6, y)
          ctx.lineTo(x, y + 6)
          ctx.lineTo(x - 6, y)
          ctx.closePath()
          ctx.fill()
          ctx.stroke()

          // Draw camera label
          ctx.fillStyle = SYSTEM_COLORS.label
          ctx.font = 'bold 10px sans-serif'
          ctx.textAlign = 'center'
          ctx.fillText(`C${cameraId}`, x, y + 18)

          // Draw point number
          ctx.fillStyle = SYSTEM_COLORS.sublabel
          ctx.font = 'bold 8px sans-serif'
          ctx.fillText((index + 1).toString(), x, y + 2)
        })
      }
    })

    // Reset text alignment
    ctx.textAlign = 'start'
  }

  // Toggle vision tracking
  const toggleVisionTracking = async () => {
    dispatch(setVisionLoading(true))
    try {
      if (isVisionEnabled) {
        // Stop tracking
        const response = await fetch('/api/cameras/tracking/stop', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' }
        })
        if (response.ok) {
          dispatch(setVisionEnabled(false))
          visionWebSocket.disconnect()
        }
      } else {
        // Start tracking
        const response = await fetch('/api/cameras/tracking/start', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' }
        })
        if (response.ok) {
          dispatch(setVisionEnabled(true))
          visionWebSocket.connect()
        }
      }
    } catch (error) {
      console.error('Failed to toggle vision tracking:', error)
    } finally {
      dispatch(setVisionLoading(false))
    }
  }

  const getButtonText = () => {
    switch (combinedStreamState) {
      case 'connecting': return 'Connecting...'
      case 'negotiating': return 'Negotiating...'
      case 'waiting_for_media': return 'Waiting for video...'
      case 'streaming': return 'Stop Combined Stream'
      case 'error': return 'Retry'
      case 'disconnected':
      default: return 'Start Combined Stream'
    }
  }

  const getVisionButtonText = () => {
    if (visionLoading) return 'Loading...'
    return isVisionEnabled ? 'Stop Vision Tracking' : 'Start Vision Tracking'
  }



  const isButtonDisabled = () => {
    return combinedStreamState === 'connecting' ||
           combinedStreamState === 'negotiating' ||
           combinedStreamState === 'waiting_for_media'
  }

  // Draw BEV tracks on canvas
  useEffect(() => {
    const canvas = bevCanvasRef.current
    if (!canvas) return

    const ctx = canvas.getContext('2d')
    if (!ctx) return

    // Clear canvas
    ctx.fillStyle = SYSTEM_COLORS.canvasBackground
    ctx.fillRect(0, 0, canvas.width, canvas.height)

    // Draw grid
    ctx.strokeStyle = SYSTEM_COLORS.gridLines
    ctx.lineWidth = 1
    ctx.setLineDash([5, 5])

    // Vertical lines
    for (let x = 0; x <= canvas.width; x += 50) {
      ctx.beginPath()
      ctx.moveTo(x, 0)
      ctx.lineTo(x, canvas.height)
      ctx.stroke()
    }

    // Horizontal lines
    for (let y = 0; y <= canvas.height; y += 50) {
      ctx.beginPath()
      ctx.moveTo(0, y)
      ctx.lineTo(canvas.width, y)
      ctx.stroke()
    }

    ctx.setLineDash([]) // Reset line dash

    // Draw coordinate labels
    ctx.fillStyle = SYSTEM_COLORS.coordinates
    ctx.font = '12px sans-serif'
    ctx.fillText('BEV Coordinates (pixels)', 10, 20)

    // Draw center point
    ctx.fillStyle = SYSTEM_COLORS.origin
    ctx.beginPath()
    ctx.arc(300, 300, 4, 0, 2 * Math.PI)
    ctx.fill()
    ctx.fillStyle = SYSTEM_COLORS.coordinates
    ctx.fillText('Center', 305, 295)

    // Draw calibration reference points
    drawCalibrationPoints(ctx)

    // Draw tracks
    tracks.forEach((track, index) => {
      const isSelected = selectedTrack === track.track_id
      const alpha = track.confidence
      const isGlobal = track.global_id !== undefined && track.global_id !== null

      // Get consistent colors from centralized system
      const trackColors = getTrackColorVariants(index, track.global_id)

      // Debug logging for selected track
      if (isSelected) {
        console.log('🎯 Selected track:', {
          id: track.track_id,
          hasTrajectory: !!track.trajectory,
          trajectoryLength: track.trajectory?.length || 0,
          trajectory: track.trajectory
        })
      }

      // Draw trajectory trail if track is selected and has trajectory data
      if (isSelected && track.trajectory && track.trajectory.length > 1) {
        ctx.strokeStyle = trackColors.trail
        ctx.lineWidth = 3
        ctx.setLineDash([5, 5])

        // Use trajectory points as BEV pixels directly
        const trajectoryPoints = track.trajectory.map(([x, y, timestamp]) => ({
          x: x, // Use BEV pixels directly
          y: y, // Use BEV pixels directly
          timestamp
        }))

        // Draw trail line
        ctx.beginPath()
        ctx.moveTo(trajectoryPoints[0].x, trajectoryPoints[0].y)
        for (let i = 1; i < trajectoryPoints.length; i++) {
          ctx.lineTo(trajectoryPoints[i].x, trajectoryPoints[i].y)
        }
        ctx.stroke()

        // Draw small circles at trajectory points with fading opacity
        const trajectoryColors = getTrajectoryColors(index, trajectoryPoints.length, track.global_id)
        trajectoryPoints.forEach((point, i) => {
          ctx.fillStyle = trajectoryColors[i]
          ctx.beginPath()
          ctx.arc(point.x, point.y, 2, 0, 2 * Math.PI)
          ctx.fill()
        })

        ctx.setLineDash([]) // Reset line dash
      }

      // Track circle
      ctx.beginPath()
      ctx.arc(track.bev_x, track.bev_y, isSelected ? 12 : 8, 0, 2 * Math.PI)

      ctx.fillStyle = `hsla(${trackColors.fill.slice(5, -1)}, ${alpha})`
      ctx.fill()

      // Border - special styling for global tracks
      if (isGlobal) {
        ctx.strokeStyle = isSelected ? SYSTEM_COLORS.selected : trackColors.stroke
        ctx.lineWidth = isSelected ? 4 : 3  // Thicker border for global tracks
      } else {
        ctx.strokeStyle = isSelected ? SYSTEM_COLORS.selected : trackColors.stroke
        ctx.lineWidth = isSelected ? 3 : 2  // Normal border for local tracks
      }
      ctx.stroke()

      // Track ID label
      ctx.fillStyle = SYSTEM_COLORS.label
      ctx.font = isSelected ? 'bold 12px sans-serif' : '10px sans-serif'
      const textWidth = ctx.measureText(track.track_id).width
      ctx.fillText(
        track.track_id,
        track.bev_x - textWidth / 2,
        track.bev_y - (isSelected ? 18 : 15)
      )

      // Confidence indicator
      if (isSelected) {
        ctx.fillStyle = SYSTEM_COLORS.singleCamera
        ctx.font = '9px sans-serif'
        ctx.fillText(
          `${(track.confidence * 100).toFixed(0)}%`,
          track.bev_x - 10,
          track.bev_y + 20
        )

        // Show if this is a cross-camera track
        if (isGlobal) {
          ctx.fillStyle = SYSTEM_COLORS.crossCamera
          ctx.fillText(
            '🔗 Cross-camera',
            track.bev_x - 25,
            track.bev_y + 32
          )
        }
      }
    })
  }, [tracks, selectedTrack, visionMetadata, calibrationData])

  // Handle canvas click for track selection
  const handleCanvasClick = (event: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = bevCanvasRef.current
    if (!canvas) return

    const rect = canvas.getBoundingClientRect()
    const x = event.clientX - rect.left
    const y = event.clientY - rect.top

    // Find clicked track
    const clickedTrack = tracks.find(track => {
      const distance = Math.sqrt(
        Math.pow(x - track.bev_x, 2) + Math.pow(y - track.bev_y, 2)
      )
      return distance <= 12 // Click tolerance
    })

    setSelectedTrack(clickedTrack ? clickedTrack.track_id : null)
  }

  return (
    <div className="space-y-6">
      {/* Header Controls */}
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <FaCrosshairs className="text-3xl" style={{ color: SYSTEM_COLORS.primary }} />
          <h1 className="text-2xl font-bold text-white">
            Combined Vision Monitoring
          </h1>
        </div>
        <div className="flex space-x-4">
          {/* Combined Stream Control */}
          <button
            onClick={onCombinedStreamToggle}
            disabled={isButtonDisabled()}
            className={`${baseButtonClass} ${
              combinedStreamState === 'streaming'
                ? 'bg-red-600 hover:bg-red-700 text-white'
                : combinedStreamState === 'error'
                ? 'bg-[#e9833a] hover:bg-[#e9833a]/80 text-white'
                : 'bg-gradient-to-r from-[#38bd85] to-[#2da89b] hover:from-[#38bd85]/80 hover:to-[#2da89b]/80 text-white disabled:bg-[#8e8e8e] disabled:cursor-not-allowed'
            }`}
          >
            {getButtonText()}
          </button>

          {/* Vision Tracking Control */}
          <button
            onClick={toggleVisionTracking}
            disabled={visionLoading || combinedStreamState !== 'streaming'}
            className={`${baseButtonClass} flex items-center justify-center gap-2 ${
              isVisionEnabled
                ? 'bg-gradient-to-r from-[#38bd85] to-[#2da89b] hover:from-[#38bd85]/80 hover:to-[#2da89b]/80 text-white'
                : 'bg-[#8e8e8e] hover:bg-[#8e8e8e]/80 text-white disabled:bg-[#8e8e8e]/70 disabled:cursor-not-allowed'
            }`}
          >
                          {visionLoading ? (
                <FaHourglassHalf className="animate-spin text-sm" />
              ) : isVisionEnabled ? (
                <FaEyeSlash className="text-sm" />
              ) : (
                <FaEye className="text-sm" />
              )}
            {getVisionButtonText()}
          </button>
        </div>
      </div>

      {/* Status Information */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-[#212121] border border-[#8e8e8e]/30 p-4 rounded-lg">
          <div className="flex items-center space-x-2 mb-2">
            <h3 className="text-sm font-medium text-[#8e8e8e]">📹 Stream Status</h3>
          </div>
          <div className="flex items-center space-x-2">
            <div className={`w-3 h-3 rounded-full ${
              combinedStreamState === 'streaming' ? 'bg-gradient-to-r from-[#38bd85] to-[#2da89b]' :
              combinedStreamState === 'error' ? 'bg-red-500' : 'bg-[#e9833a]'
            }`}></div>
            <span className="text-white capitalize">{combinedStreamState.replace('_', ' ')}</span>
          </div>
        </div>

        <div className="bg-[#212121] border border-[#8e8e8e]/30 p-4 rounded-lg">
          <div className="flex items-center space-x-2 mb-2">
                          <FaRoute className="text-[#8e8e8e] text-sm" />
            <h3 className="text-sm font-medium text-[#8e8e8e]">Vision Tracking</h3>
          </div>
          <div className="flex items-center space-x-2">
            <div className={`w-3 h-3 rounded-full ${
              isVisionEnabled && visionWebSocketConnected ? 'bg-gradient-to-r from-[#38bd85] to-[#2da89b]' : 'bg-[#8e8e8e]'
            }`}></div>
            <span className="text-white">
              {isVisionEnabled ? 'Active' : 'Inactive'}
              {isVisionEnabled && !visionWebSocketConnected && ' (Disconnected)'}
            </span>
          </div>
        </div>

        <div className="bg-[#212121] border border-[#8e8e8e]/30 p-4 rounded-lg">
          <div className="flex items-center space-x-2 mb-2">
            <h3 className="text-sm font-medium text-[#8e8e8e]">📊 Detection Stats</h3>
          </div>
          <div className="text-white text-lg font-semibold">
            {tracks.length} BEV Tracks
            {visionMetadata && (
              <>
                <div className="text-sm text-[#8e8e8e] mt-1">
                  Streams: {visionMetadata.num_streams || 2} | Frame {visionMetadata.frame_id}
                </div>
                {visionMetadata.all_streams && (
                  <div className="text-xs text-[#8e8e8e] mt-1">
                    Total: {Object.values(visionMetadata.all_streams).reduce((sum: number, stream: any) => sum + stream.detections.length, 0)} detections
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      </div>

      {/* Stream Synchronization Controls */}
      <div className="space-y-4">
        <h2 className="text-lg font-semibold">⏱️ Stream Synchronization</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
          {cameras.map((camera) => (
            <StreamDelayControls
              key={camera.id}
              streamId={camera.id}
              streamName={camera.name}
              disabled={combinedStreamState !== 'streaming'}
            />
          ))}
        </div>
        {combinedStreamState !== 'streaming' && (
          <p className="text-sm text-[#8e8e8e] text-center">
            Start the combined stream to adjust synchronization delays
          </p>
        )}
      </div>

      {/* Vision & Tracking Controls */}
      <div className="space-y-2">
        <button
          onClick={() => setVisionControlsVisible(!visionControlsVisible)}
          className="flex items-center justify-between w-full text-lg font-semibold text-left"
        >
          <span>⚙️ Vision & Tracking Controls</span>
                      <FaChevronDown className={`w-5 h-5 transition-transform ${visionControlsVisible ? 'transform rotate-180' : ''}`} />
        </button>
        {visionControlsVisible && <VisionProcessorControls />}
      </div>

      {/* Main Content - Side by Side */}
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
        {/* Camera Feeds */}
        <div className="space-y-4">
          <h2 className="text-xl font-semibold">📹 Camera Feeds</h2>
          <div className="relative bg-black rounded-lg overflow-hidden flex justify-center max-w-none">
            {/* Combined video element at native resolution */}
            <video
              ref={videoRef}
              id="combined-video-main"
              className="block"
              autoPlay
              muted
              playsInline
              style={{
                display: combinedStreamState === 'streaming' ? 'block' : 'none',
                width: `${scaledCombinedResolution.width}px`,
                height: `${scaledCombinedResolution.height}px`,
                objectFit: 'contain'
              }}
            />

            {/* Multi-Stream Vision Overlay */}
            {combinedStreamState === 'streaming' && isVisionEnabled && (
              <MultiStreamVisionOverlay
                videoRef={videoRef}
                visionData={visionMetadata}
              />
            )}

            {/* Loading and error overlays */}
            <StreamLoadingOverlay state={combinedStreamState} />
            <StreamErrorOverlay
              error={combinedStreamError || null}
              isVisible={combinedStreamState === 'error'}
              onRetry={onRetryCombinedStream}
            />

            {/* When no stream, show placeholder */}
            {combinedStreamState === 'disconnected' && (
              <div
                className="absolute inset-0 flex items-center justify-center bg-black"
                                  style={{
                    width: `${scaledCombinedResolution.width}px`,
                    height: `${scaledCombinedResolution.height}px`,
                    margin: '0 auto'
                  }}
              >
                <div className="text-center">
                  <div className="text-4xl mb-2">📹</div>
                  <div className="text-white text-lg mb-2">Combined Camera Stream</div>
                  <div className="text-[#8e8e8e] text-sm">
                    Native Resolution: {combinedResolution.width}x{combinedResolution.height}
                    ({individualResolution.width}x{individualResolution.height} per camera)
                  </div>
                  <div className="text-[#8e8e8e] text-sm">Click "Start Combined Stream" to begin</div>
                </div>
              </div>
            )}

            {/* Multi-Stream labels and stats overlay */}
            {combinedStreamState === 'streaming' && visionMetadata && (
              <div className="absolute inset-0 pointer-events-none">
                {(visionMetadata.active_stream_ids || [0, 1]).map((streamId: number, index: number) => {
                  const numStreams = visionMetadata.num_streams || 2
                  const gridCols = numStreams === 1 ? 1 : numStreams <= 2 ? 2 : 2

                  // Calculate position in grid
                  const col = index % gridCols
                  const row = Math.floor(index / gridCols)

                  // Position label in appropriate corner of each stream
                  const isTopRow = row === 0
                  const isLeftCol = col === 0

                  let positionClasses = 'absolute '
                  if (isTopRow && isLeftCol) {
                    positionClasses += 'top-4 left-4'
                  } else if (isTopRow && !isLeftCol) {
                    positionClasses += 'top-4 right-4'
                  } else if (!isTopRow && isLeftCol) {
                    positionClasses += 'bottom-4 left-4'
                  } else {
                    positionClasses += 'bottom-4 right-4'
                  }


                  const camera = cameras.find(c => c.id === streamId)

                  return (
                    <div key={streamId} className={`${positionClasses} bg-black bg-opacity-75 text-white px-3 py-2 rounded-lg`}>
                      <div className="font-semibold text-sm flex items-center">
                        <span className={`w-2 h-2 rounded-full mr-2 ${
                          index === 0 ? 'bg-green-400' :
                          index === 1 ? 'bg-blue-400' :
                          index === 2 ? 'bg-yellow-400' : 'bg-purple-400'
                        }`}></span>
                        📹 Stream {streamId}
                      </div>
                      <div className="text-xs text-[#8e8e8e] mt-1">
                        {camera?.name || `Camera ${streamId}`}
                      </div>

                    </div>
                  )
                })}
              </div>
            )}
          </div>
        </div>

        {/* Bird's Eye View */}
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-xl font-semibold">🗺️ Bird's Eye View</h2>
            <div className="flex items-center space-x-4">
              <span className="text-sm text-[#8e8e8e]">
                Active Tracks: <span className="text-transparent bg-gradient-to-r from-[#38bd85] to-[#2da89b] bg-clip-text font-semibold">{tracks.length}</span>
              </span>
              <div className={`flex items-center space-x-2 text-xs ${visionWebSocketConnected ? 'text-transparent bg-gradient-to-r from-[#38bd85] to-[#2da89b] bg-clip-text' : 'text-[#8e8e8e]'}`}>
                <div className={`w-2 h-2 rounded-full ${visionWebSocketConnected ? 'bg-gradient-to-r from-[#38bd85] to-[#2da89b] animate-pulse' : 'bg-[#8e8e8e]'}`}></div>
                <span>{visionWebSocketConnected ? 'Live Vision Data' : 'Vision Disconnected'}</span>
              </div>
              {selectedTrack && (
                <button
                  onClick={() => setSelectedTrack(null)}
                  className="px-3 py-1 bg-[#8e8e8e] text-white text-sm rounded hover:bg-[#8e8e8e]/80 transition-colors"
                >
                  Clear Selection
                </button>
              )}
            </div>
          </div>

          <div className="bg-[#212121] border border-[#8e8e8e]/30 rounded-lg p-4">
            <canvas
              ref={bevCanvasRef}
              className="w-full cursor-pointer bg-[#1a1a1a] rounded"
              width="600"
              height="600"
              onClick={handleCanvasClick}
            />
            <p className="text-xs text-[#8e8e8e] mt-2">
              Click on tracks to select them and see trajectory trail • Grid represents BEV pixel coordinates •
              <span className="text-transparent bg-gradient-to-r from-[#38bd85] to-[#2da89b] bg-clip-text">Diamond markers show calibration reference points (C0, C1, etc.)</span>
            </p>
          </div>

          {/* Track Details */}
          {selectedTrack && (
            <div className="bg-[#212121] border border-[#8e8e8e]/30 rounded-lg p-4">
              <div className="flex items-center space-x-2 mb-2">
                <h3 className="text-lg font-semibold">🔗 Selected Track: {selectedTrack}</h3>
              </div>
              {(() => {
                const track = tracks.find(t => t.track_id === selectedTrack)
                if (!track) return null

                return (
                  <div className="text-sm space-y-2">
                    <div>
                      <span className="text-[#8e8e8e]">Position:</span>{' '}
                      <span className="text-white">
                        ({track.bev_x.toFixed(0)}px, {track.bev_y.toFixed(0)}px)
                      </span>
                    </div>
                    <div>
                      <span className="text-[#8e8e8e]">Distance from center:</span>{' '}
                      <span className="text-white">
                        {(Math.sqrt(Math.pow(track.bev_x - 300, 2) + Math.pow(track.bev_y - 300, 2))).toFixed(0)}px
                      </span>
                    </div>
                    <div>
                      <span className="text-[#8e8e8e]">Confidence:</span>{' '}
                      <span className="text-white">{(track.confidence * 100).toFixed(0)}%</span>
                    </div>
                    {track.trajectory && track.trajectory.length > 1 && (
                      <>
                        <div>
                          <span className="text-[#8e8e8e]">Trajectory points:</span>{' '}
                          <span className="text-white">{track.trajectory.length}</span>
                        </div>
                        <div>
                          <span className="text-[#8e8e8e]">Track duration:</span>{' '}
                          <span className="text-white">
                            {((track.trajectory[track.trajectory.length - 1][2] - track.trajectory[0][2]) / 1000).toFixed(1)}s
                          </span>
                        </div>
                      </>
                    )}
                  </div>
                )
              })()}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

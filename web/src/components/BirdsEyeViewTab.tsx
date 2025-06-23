import { useEffect, useRef, useState } from 'react'
import type { BEVTrack } from '../types'
import type { VisionMetadata } from '../services/VisionWebSocket'
import { useAppSelector } from '../store/hooks'
import {
  getCameraColorVariants,
  getTrackColorVariants,
  getCalibrationPointColor,
  SYSTEM_COLORS
} from '../utils/colors'
import {
  ChartBarIcon,
  MapIcon,
  InformationCircleIcon
} from '@heroicons/react/24/outline'

interface BirdsEyeViewTabProps {
  // No props needed - using Redux state
}

export function BirdsEyeViewTab({ }: BirdsEyeViewTabProps) {
  // Redux state selectors
  const visionMetadata = useAppSelector(state => state.vision.visionMetadata)
  const visionWebSocketConnected = useAppSelector(state => state.vision.webSocketConnected)
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const [selectedTrack, setSelectedTrack] = useState<string | null>(null)
  const [calibrationData, setCalibrationData] = useState<any>(null)
  const [debugTransformData, setDebugTransformData] = useState<any>(null)
  const [showDebugPoints, setShowDebugPoints] = useState(false)

  // Debug state changes
  useEffect(() => {
    console.log('🔍 STATE CHANGE - debugTransformData:', debugTransformData)
  }, [debugTransformData])

  useEffect(() => {
    console.log('🔍 STATE CHANGE - showDebugPoints:', showDebugPoints)
  }, [showDebugPoints])

  // Helper function to get the display ID for a track
  const getTrackDisplayId = (visionTrack: any): string => {
    if (visionTrack.global_id !== undefined && visionTrack.global_id !== null) {
      return `global_${visionTrack.global_id}`
    }
    return visionTrack.id
  }

  // Helper function to get a consistent color for a track
  const getTrackColorValue = (visionTrack: any, index: number): number => {
    if (visionTrack.global_id !== undefined && visionTrack.global_id !== null) {
      // Use global_id for consistent colors across cameras
      return (visionTrack.global_id * 137.5) % 360
    }
    // Fallback to index-based coloring
    return (index * 137.5) % 360
  }

  // Log the raw vision metadata for debugging
  useEffect(() => {
    if (visionMetadata?.bev_tracks) {
      console.log('🔍 RAW VISION METADATA:', {
        frame_id: visionMetadata.frame_id,
        total_bev_tracks: visionMetadata.bev_tracks.length,
        bev_tracks: visionMetadata.bev_tracks
      })
    }
  }, [visionMetadata])

  // Transform vision tracks to BEV format
  const tracks: BEVTrack[] = visionMetadata?.bev_tracks.map((visionTrack, index) => {
    // Backend already outputs absolute pixel coordinates in 600x600 space
    // Calibration points are normalized [0-1] then multiplied by 600
    // So we need to use backend coordinates directly since they're already pixels

    console.log(`🔍 BEV TRACK ${index} - USING DIRECT PIXELS:`, {
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
      global_id: visionTrack.global_id
    }
  }) || []

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

  // Function to fetch debug transform data
  const fetchDebugTransformData = async () => {
    try {
      console.log('🔍 Fetching debug transform data...')
      const response = await fetch('/api/calibration/debug-transform-calibration-points')
      console.log('🔍 Response status:', response.status)

      if (response.ok) {
        const data = await response.json()
        console.log('🔍 Raw API response:', data)

        if (data.success) {
          setDebugTransformData(data.transformed_points)
          setShowDebugPoints(true)
          console.log('🔍 DEBUG TRANSFORM DATA SET:', data.transformed_points)
          console.log('🔍 Show debug points:', true)
        } else {
          console.log('🔍 API returned success=false:', data.message)
        }
      } else {
        console.log('🔍 API request failed:', response.status, response.statusText)
      }
    } catch (error) {
      console.error('🔍 Failed to load debug transform data:', error)
    }
  }

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

          console.log(`🔍 CALIBRATION POINT ${index} - Camera ${cameraId}:`, {
            normalized: point,
            canvas_coords: [x, y]
          })

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

  // Function to draw debug transformed points
  const drawDebugTransformedPoints = (ctx: CanvasRenderingContext2D) => {
    console.log('🔍 drawDebugTransformedPoints called')
    console.log('🔍 debugTransformData:', debugTransformData)
    console.log('🔍 showDebugPoints:', showDebugPoints)

    if (!debugTransformData) {
      console.log('🔍 No debugTransformData - returning')
      return
    }

    console.log('🔍 Processing debug transform data entries:', Object.keys(debugTransformData))

    Object.entries(debugTransformData).forEach(([cameraKey, cameraData]: [string, any]) => {
      const cameraId = cameraData.camera_id
      const backendTransformedPixels = cameraData.backend_transformed_pixels

      console.log(`🔍 Processing camera ${cameraKey}:`, {
        cameraId,
        backendTransformedPixels,
        isArray: Array.isArray(backendTransformedPixels)
      })

      if (backendTransformedPixels && Array.isArray(backendTransformedPixels)) {
        backendTransformedPixels.forEach((point: [number, number], index: number) => {
          const x = point[0]
          const y = point[1]

          console.log(`🔍 DEBUG TRANSFORMED POINT ${index} - Camera ${cameraId}:`, {
            backend_pixels: point,
            canvas_coords: [x, y]
          })

          // Draw transformed point with distinct styling (star shape)
          ctx.fillStyle = '#ff0000' // Bright red for debug points
          ctx.strokeStyle = '#ffffff' // White border
          ctx.lineWidth = 2

          // Draw star shape for debug points
          const size = 8
          ctx.beginPath()
          for (let i = 0; i < 5; i++) {
            const angle = (i * 144) * Math.PI / 180
            const radius = i % 2 === 0 ? size : size / 2
            const pointX = x + Math.cos(angle) * radius
            const pointY = y + Math.sin(angle) * radius
            if (i === 0) {
              ctx.moveTo(pointX, pointY)
            } else {
              ctx.lineTo(pointX, pointY)
            }
          }
          ctx.closePath()
          ctx.fill()
          ctx.stroke()

          // Draw debug label
          ctx.fillStyle = '#ffffff'
          ctx.font = 'bold 10px sans-serif'
          ctx.textAlign = 'center'
          ctx.fillText(`T${cameraId}-${index + 1}`, x, y - 15)
        })
      }
    })

    // Reset text alignment
    ctx.textAlign = 'start'
  }

  // Draw tracks on canvas
  useEffect(() => {
    const canvas = canvasRef.current
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
    ctx.fillText('BEV Coordinates (pixels) - Live Vision Data', 10, 20)
    ctx.fillText('Top-Left: (0,0)', 10, canvas.height - 10)
    ctx.fillText('Bottom-Right: (600,600)', canvas.width - 120, canvas.height - 10)

    // Draw center point
    ctx.fillStyle = SYSTEM_COLORS.origin
    ctx.beginPath()
    ctx.arc(300, 300, 4, 0, 2 * Math.PI)
    ctx.fill()
    ctx.fillStyle = SYSTEM_COLORS.coordinates
    ctx.fillText('Center', 305, 295)

    // Draw calibration reference points
    drawCalibrationPoints(ctx)

    // Draw debug transformed points if enabled
    console.log('🔍 Checking debug points:', { showDebugPoints, hasDebugData: !!debugTransformData })
    if (showDebugPoints && debugTransformData) {
      console.log('🔍 About to draw debug transformed points')
      drawDebugTransformedPoints(ctx)
    } else {
      console.log('🔍 Not drawing debug points:', { showDebugPoints, hasDebugData: !!debugTransformData })
    }

    // Draw tracks
    tracks.forEach((track, index) => {
      console.log(`🎯 DRAWING TRACK ${track.track_id}:`, {
        canvas_coords: [track.bev_x, track.bev_y],
        canvas_size: [canvas.width, canvas.height]
      })

      const isSelected = selectedTrack === track.track_id
      const alpha = track.confidence
      const isGlobal = track.global_id !== undefined && track.global_id !== null

      // Get consistent colors from centralized system
      const trackColors = getTrackColorVariants(index, track.global_id)

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

      // Confidence and global ID indicator
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
  }, [tracks, selectedTrack, visionMetadata, calibrationData, debugTransformData, showDebugPoints])

  // Handle canvas click for track selection
  const handleCanvasClick = (event: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current
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

  // Clear selected track
  const clearSelection = () => {
    setSelectedTrack(null)
  }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
      <div className="lg:col-span-2">
        <div className="bg-[#212121] border border-[#8e8e8e]/30 rounded-lg p-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-semibold">🗺️ Bird's Eye View Tracking</h3>
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
                  onClick={clearSelection}
                  className="px-3 py-1 bg-[#8e8e8e] text-white text-sm rounded hover:bg-[#8e8e8e]/80 transition-colors"
                >
                  Clear Selection
                </button>
              )}
              <button
                onClick={fetchDebugTransformData}
                className="px-3 py-1 bg-gradient-to-r from-[#38bd85] to-[#2da89b] hover:from-[#38bd85]/80 hover:to-[#2da89b]/80 text-white text-sm rounded transition-colors"
              >
                🔍 Debug Transform
              </button>
              <button
                onClick={() => {
                  // Force test data to check if drawing works
                  console.log('🔍 FORCING TEST DEBUG DATA')
                  setDebugTransformData({
                    camera0: {
                      camera_id: 0,
                      backend_transformed_pixels: [[100, 100], [200, 200], [300, 300], [400, 400]]
                    }
                  })
                  setShowDebugPoints(true)
                }}
                className="px-3 py-1 bg-[#e9833a] hover:bg-[#e9833a]/80 text-white text-sm rounded transition-colors"
              >
                🧪 Test Draw
              </button>
              {showDebugPoints && (
                <button
                  onClick={() => setShowDebugPoints(false)}
                  className="px-3 py-1 bg-red-600 hover:bg-red-700 text-white text-sm rounded transition-colors"
                >
                  Hide Debug
                </button>
              )}
            </div>
          </div>
          <canvas
            ref={canvasRef}
            id="bevCanvas"
            className="bev-canvas w-full cursor-pointer"
            width="600"
            height="600"
            onClick={handleCanvasClick}
          />
          <p className="text-xs text-[#8e8e8e] mt-2">
            Click on tracks to select them • Grid represents BEV pixel coordinates •
            <span className="text-transparent bg-gradient-to-r from-[#38bd85] to-[#2da89b] bg-clip-text">Diamond markers show calibration reference points (C0, C1, etc.)</span>
            {showDebugPoints && (
              <><br /><span className="text-red-400">Red stars show where backend transforms calibration image points</span></>
            )}
          </p>
        </div>
      </div>

      <div>
        <div className="bg-[#212121] border border-[#8e8e8e]/30 rounded-lg p-6">
          <h4 className="text-md font-semibold mb-4">📋 Active Tracks</h4>
          <div className="space-y-3 max-h-96 overflow-y-auto">
            {tracks.length === 0 ? (
              <div className="text-center py-4">
                <p className="text-[#8e8e8e] mb-2">No active tracks</p>
                {!visionWebSocketConnected ? (
                  <p className="text-xs text-red-400">Vision system disconnected</p>
                ) : (
                  <p className="text-xs text-[#8e8e8e]">Waiting for vision detection...</p>
                )}
              </div>
            ) : (
              tracks
                .sort((a, b) => a.track_id.localeCompare(b.track_id))
                .map((track, index) => {
                  const isSelected = selectedTrack === track.track_id
                  const isGlobal = track.global_id !== undefined && track.global_id !== null
                  const trackColors = getTrackColorVariants(index, track.global_id)

                  return (
                    <div
                      key={track.track_id}
                      className={`p-3 rounded border cursor-pointer transition-all ${
                        isSelected
                          ? 'border-white bg-[#2a2a2a]'
                          : 'border-[#8e8e8e]/30 bg-[#1a1a1a] hover:border-[#8e8e8e]/50'
                      }`}
                      onClick={() => setSelectedTrack(isSelected ? null : track.track_id)}
                    >
                      <div className="flex items-center justify-between mb-2">
                        <div className="flex items-center space-x-2">
                          <div
                            className="w-3 h-3 rounded-full"
                            style={{ backgroundColor: trackColors.fill }}
                          />
                          <span className="font-medium text-sm">{track.track_id}</span>
                          {isGlobal && (
                            <span
                              className="text-xs px-1 py-0.5 text-white rounded bg-gradient-to-r from-[#38bd85] to-[#2da89b]"
                              title="Cross-camera track"
                            >
                              🔗
                            </span>
                          )}
                        </div>
                        <span
                          className="text-xs px-2 py-1 text-white rounded bg-gradient-to-r from-[#38bd85] to-[#2da89b]"
                        >
                          {(track.confidence * 100).toFixed(0)}%
                        </span>
                      </div>
                      <div className="text-xs text-[#8e8e8e] space-y-1">
                        {/* Display BEV pixel coordinates */}
                        <div>Position: ({track.bev_x.toFixed(0)}px, {track.bev_y.toFixed(0)}px)</div>
                        <div>Distance from center: {(Math.sqrt(Math.pow(track.bev_x - 300, 2) + Math.pow(track.bev_y - 300, 2))).toFixed(0)}px</div>
                      </div>
                    </div>
                  )
                })
            )}
          </div>
        </div>

        <div className="bg-[#212121] border border-[#8e8e8e]/30 rounded-lg p-6 mt-6">
                          <div className="flex items-center space-x-2 mb-4">
                  <ChartBarIcon className="w-5 h-5" style={{ color: SYSTEM_COLORS.info }} />
                  <h4 className="text-md font-semibold" style={{ color: SYSTEM_COLORS.label }}>
                    Statistics
                  </h4>
                </div>
          <div className="space-y-3 text-sm">
            <div className="flex justify-between">
              <span className="text-gray-400">Total Tracks:</span>
              <span className="text-white font-medium">{tracks.length}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-400">Avg Confidence:</span>
              <span className="text-white font-medium">
                {tracks.length > 0
                  ? `${((tracks.reduce((sum, t) => sum + t.confidence, 0) / tracks.length) * 100).toFixed(0)}%`
                  : 'N/A'
                }
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-400">Selected Track:</span>
              <span className="text-white font-medium">
                {selectedTrack || 'None'}
              </span>
            </div>
            {visionMetadata && (
              <>
                <div className="flex justify-between">
                  <span className="text-gray-400">Frame ID:</span>
                  <span className="text-white font-medium">
                    {visionMetadata.frame_id}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-400">Processing Time:</span>
                  <span className="text-white font-medium">
                    {visionMetadata.processing_time_ms.toFixed(1)}ms
                  </span>
                </div>
              </>
            )}
            <div className="pt-2 border-t border-gray-700">
              <div className={`flex items-center space-x-2 text-xs ${visionWebSocketConnected ? 'text-green-400' : 'text-red-400'}`}>
                <div className={`w-2 h-2 rounded-full ${visionWebSocketConnected ? 'bg-green-500 animate-pulse' : 'bg-red-500'}`}></div>
                <span>{visionWebSocketConnected ? 'Vision system active' : 'Vision system disconnected'}</span>
              </div>
            </div>
          </div>
        </div>

        <div className="bg-[#212121] border border-[#8e8e8e]/30 rounded-lg p-6 mt-6">
                          <div className="flex items-center space-x-2 mb-4">
                  <MapIcon className="w-5 h-5" style={{ color: SYSTEM_COLORS.info }} />
                  <h4 className="text-md font-semibold" style={{ color: SYSTEM_COLORS.label }}>
                    BEV Legend
                  </h4>
                </div>
          <div className="space-y-2 text-sm">
            <div className="flex items-center space-x-3">
              <div className="w-4 h-4 rounded-full bg-blue-500"></div>
              <span className="text-gray-300">Live tracked objects</span>
            </div>
            <div className="flex items-center space-x-3">
              <div className="w-0 h-0 border-l-[6px] border-r-[6px] border-b-[8px] border-l-transparent border-r-transparent border-b-orange-400 rotate-45"></div>
              <span className="text-gray-300">Calibration reference points</span>
            </div>
            <div className="flex items-center space-x-3">
              <div className="w-4 h-1 bg-green-500 rounded"></div>
              <span className="text-gray-300">Cross-camera tracks</span>
            </div>
            <div className="flex items-center space-x-3">
              <div className="w-2 h-2 rounded-full bg-blue-400"></div>
              <span className="text-gray-300">Canvas center (300,300)</span>
            </div>
            {showDebugPoints && (
              <div className="flex items-center space-x-3">
                <div className="w-4 h-4 flex items-center justify-center">
                  <span className="text-red-500 text-lg">★</span>
                </div>
                <span className="text-gray-300">Backend transformed points (debug)</span>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

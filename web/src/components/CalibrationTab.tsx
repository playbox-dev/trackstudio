import React, { useRef, useEffect, useCallback } from 'react'
import { LoadingSpinner } from './LoadingSpinner'
import type { CombinedStreamState } from '../types'
import { useAppDispatch, useAppSelector } from '../store/hooks'
import {
  getCameraColorVariants,
  getCalibrationPointColor,
  SYSTEM_COLORS
} from '../utils/colors'
import {
  CheckCircleIcon,
  CameraIcon
} from '@heroicons/react/24/outline'
import {
  setFrames,
  setLoading,
  setSelectedCamera,
  setIsCalibrating,
  addImagePoint,
  addBevPoint,
  setImagePoints,
  setCalibrationResult,
  resetPoints,
  resetAllCalibration,
  loadCalibrationData,
  addToHistory,
  undo,
  redo
} from '../store/slices/calibrationSlice'
import { fetchCameraConfig } from '../store/slices/cameraConfigSlice'

interface Point {
  x: number
  y: number
}


interface CalibrationTabProps {
  combinedStreamState: CombinedStreamState
  onSwitchToStreams: () => void
}

export function CalibrationTab({ combinedStreamState, onSwitchToStreams }: CalibrationTabProps) {
  const dispatch = useAppDispatch()

  // Redux state selectors
  const frames = useAppSelector(state => state.calibration.frames)
  const loading = useAppSelector(state => state.calibration.loading)
  const selectedCamera = useAppSelector(state => state.calibration.selectedCamera)
  const isCalibrating = useAppSelector(state => state.calibration.isCalibrating)
  const imagePoints = useAppSelector(state => state.calibration.imagePoints)
  const bevPoints = useAppSelector(state => state.calibration.bevPoints)
  const cameraBevPoints = useAppSelector(state => state.calibration.cameraBevPoints)
  const calibrationResult = useAppSelector(state => state.calibration.calibrationResult)
  const calibratedCameras = useAppSelector(state => state.calibration.calibratedCameras)
  const calibrationResults = useAppSelector(state => state.calibration.calibrationResults)
  const calibrationCompletedAt = useAppSelector(state => state.calibration.calibrationCompletedAt)
  const history = useAppSelector(state => state.calibration.history)
  const historyIndex = useAppSelector(state => state.calibration.historyIndex)

  // Refs for canvas elements
  const imageCanvasRef = useRef<HTMLCanvasElement>(null)
  const bevCanvasRef = useRef<HTMLCanvasElement>(null)

  // Check if stream is ready for calibration
  const isStreamReady = combinedStreamState === 'streaming'

  // Check if calibration is complete (all cameras calibrated)
  const calibrationMaxCameras = useAppSelector(state => state.calibration.maxCameras)
  const configuredCameras = useAppSelector(state => state.cameraConfig.cameras)
  // Use configured cameras count if available, otherwise fall back to calibration maxCameras
  const maxCameras = configuredCameras.length > 0 ? configuredCameras.length : calibrationMaxCameras
  const isCalibrationComplete = calibratedCameras.length === maxCameras

  // Format completion time
  const formatCompletionTime = (dateString: string) => {
    const date = new Date(dateString)
    return date.toLocaleString('en-US', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit'
    })
  }

  // Handle keyboard shortcuts (Ctrl+Z / Cmd+Z for undo, Ctrl+Shift+Z / Cmd+Shift+Z for redo)
  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      // Check if Ctrl/Cmd is pressed
      if (event.ctrlKey || event.metaKey) {
        if (event.key.toLowerCase() === 'z') {
          if (event.shiftKey) {
            // Redo: Ctrl+Shift+Z (Windows/Linux) or Cmd+Shift+Z (Mac)
            event.preventDefault()

            // Check if we can redo
            const canRedo = historyIndex < history.length - 1
            if (canRedo) {
              dispatch(redo())
            }
          } else {
            // Undo: Ctrl+Z (Windows/Linux) or Cmd+Z (Mac)
            event.preventDefault()

            // Check if we can undo
            const canUndo = historyIndex === -1 ? history.length > 0 : historyIndex >= 0
            if (canUndo) {
              dispatch(undo())
            }
          }
        }
      }
    }

    // Add event listener
    window.addEventListener('keydown', handleKeyDown)

    // Cleanup
    return () => {
      window.removeEventListener('keydown', handleKeyDown)
    }
  }, [dispatch, history.length, historyIndex])

  // Capture frames from cameras
  const handleCaptureFrames = async () => {
    if (!isStreamReady) {
      alert('Please start the combined video stream first before capturing frames for calibration.')
      return
    }

    dispatch(setLoading(true))
    try {
      const response = await fetch('/api/calibration/capture-frames')

      if (!response.ok) {
        const errorData = await response.json()
        console.error('HTTP Error:', response.status, errorData)
        const errorMessage = errorData.detail || errorData.message || `HTTP ${response.status} error`
        alert(`Failed to capture frames: ${errorMessage}`)
        return
      }

      const data = await response.json()

      if (data.success) {
        dispatch(setFrames(data))
        // Reset points when new frames are captured
        dispatch(setImagePoints([]))
        // Keep individual camera BEV points when capturing new frames
        dispatch(setCalibrationResult(null))
      } else {
        console.error('Failed to capture frames:', data)
        alert(`Failed to capture frames: ${data.detail || data.message || 'Unknown error'}`)
      }
    } catch (error) {
      console.error('Error capturing frames:', error)
      alert(`Error capturing frames: ${error}`)
    } finally {
      dispatch(setLoading(false))
    }
  }

  // Handle image canvas click
  const handleImageClick = (event: React.MouseEvent<HTMLCanvasElement>) => {
    if (imagePoints.length >= 4) return

    const canvas = imageCanvasRef.current
    if (!canvas) return

    const rect = canvas.getBoundingClientRect()
    const x = event.clientX - rect.left
    const y = event.clientY - rect.top

    // Convert to original image coordinates (pixels)
    const imageX = (x / rect.width) * (frames?.frame_width || 640)
    const imageY = (y / rect.height) * (frames?.frame_height || 480)
    const point = { x: imageX, y: imageY }

    // Add to history before adding the point
    dispatch(addToHistory({
      type: 'image',
      point,
      camera: selectedCamera
    }))

    dispatch(addImagePoint(point))
  }

  // Handle BEV canvas click
  const handleBevClick = (event: React.MouseEvent<HTMLCanvasElement>) => {
    if (bevPoints.length >= 4) return  // Only check current camera's point count

    const canvas = bevCanvasRef.current
    if (!canvas) return

    const rect = canvas.getBoundingClientRect()
    const x = event.clientX - rect.left
    const y = event.clientY - rect.top

    // Convert to normalized BEV coordinates [0-1]
    const bevX = x / canvas.width
    const bevY = y / canvas.height
    const point = { x: bevX, y: bevY }

    // Add to history before adding the point
    dispatch(addToHistory({
      type: 'bev',
      point,
      camera: selectedCamera
    }))

    dispatch(addBevPoint(point))
  }

  // Handle camera selection change
  const handleCameraChange = (newCameraId: 0 | 1 | 2 | 3) => {
    dispatch(setSelectedCamera(newCameraId))
  }

  // Reset points handler
  const handleResetPoints = () => {
    dispatch(resetPoints())
  }

  // Reset all calibration handler
  const handleResetAllCalibration = () => {
    dispatch(resetAllCalibration())
  }

  // Perform calibration
  const handlePerformCalibration = async () => {
    if (imagePoints.length !== 4 || bevPoints.length !== 4) {
      alert('Please select exactly 4 points on both image and BEV map')
      return
    }

    if (!isStreamReady) {
      alert('Video stream is no longer active. Please restart the stream and capture new frames.')
      return
    }

    dispatch(setIsCalibrating(true))
    try {
      const pointPairs = imagePoints.map((imagePoint, index) => ({
        image_point: [imagePoint.x, imagePoint.y],
        bev_point: [bevPoints[index].x, bevPoints[index].y]
      }))

      const response = await fetch('/api/calibration/calibrate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          camera_id: selectedCamera,
          point_pairs: pointPairs
        })
      })

      if (!response.ok) {
        const errorData = await response.json()
        console.error('HTTP Error:', response.status, errorData)
        const errorMessage = errorData.detail || errorData.message || `HTTP ${response.status} error`
        dispatch(setCalibrationResult({
          success: false,
          message: `Calibration failed: ${errorMessage}`
        }))
        return
      }

      const result = await response.json()
      dispatch(setCalibrationResult(result))

      if (result.success) {
        console.log('Calibration successful:', result.message)
        // The Redux reducer will handle updating calibrated cameras and results
      } else {
        console.error('Calibration failed:', result.message)
      }
    } catch (error) {
      console.error('Error during calibration:', error)
      dispatch(setCalibrationResult({
        success: false,
        message: `Calibration error: ${error}`
      }))
    } finally {
      dispatch(setIsCalibrating(false))
    }
  }

  // Draw points on canvas
  const drawPoints = (canvas: HTMLCanvasElement, points: Point[], clearCanvas = true, isImageCanvas = false) => {
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    if (clearCanvas) {
      ctx.clearRect(0, 0, canvas.width, canvas.height)
    }

    points.forEach((point, index) => {
      let x, y

      if (isImageCanvas) {
        // Image points are in pixel coordinates, canvas now matches frame dimensions
        x = point.x
        y = point.y
      } else {
        // BEV points are normalized [0-1], scale to canvas size
        x = point.x * canvas.width
        y = point.y * canvas.height
      }

      // Draw point
      ctx.fillStyle = getCalibrationPointColor(index, 1.0)
      ctx.beginPath()
      ctx.arc(x, y, 8, 0, 2 * Math.PI)
      ctx.fill()

      // Draw point number
      ctx.fillStyle = SYSTEM_COLORS.label
      ctx.font = 'bold 12px Arial'
      ctx.textAlign = 'center'
      ctx.fillText((index + 1).toString(), x, y + 4)
    })
  }

  // Draw BEV grid with multiple camera overlays and reference points
  const drawBevGrid = useCallback((canvas: HTMLCanvasElement) => {
    console.log('🎯 drawBevGrid called', { canvasWidth: canvas.width, canvasHeight: canvas.height, calibrationResultsCount: Object.keys(calibrationResults).length })
    const ctx = canvas.getContext('2d')
    if (!ctx) {
      console.error('🎯 Failed to get canvas context')
      return
    }

    ctx.clearRect(0, 0, canvas.width, canvas.height)

    // ALWAYS draw grid background and overlay first - this is the base layer
    ctx.fillStyle = SYSTEM_COLORS.canvasBackground
    ctx.fillRect(0, 0, canvas.width, canvas.height)

    console.log('🎯 Drawing base grid overlay')
    drawGridOverlay(ctx, canvas.width, canvas.height)

    // Draw all calibrated camera overlays ON TOP of the grid
    const calibratedEntries = Object.entries(calibrationResults)

    if (calibratedEntries.length > 0) {
      const totalImages = calibratedEntries.filter(([_, result]) => result.success && result.transformed_image_base64).length

      if (totalImages === 0) {
        // No images to load, just draw points on top of grid
        console.log('🎯 No images to load, drawing points on grid')
        drawAllCameraBevPoints(canvas)
      } else {
        // Load and draw calibration overlay images
        let imagesLoaded = 0
        calibratedEntries.forEach(([cameraIdStr, result]) => {
          const cameraId = parseInt(cameraIdStr)
          if (result.success && result.transformed_image_base64) {
            const img = new Image()
            img.onload = () => {
              // Set opacity based on camera and whether it's currently selected
              if (cameraId === selectedCamera) {
                ctx.globalAlpha = 0.8 // Current camera more opaque
              } else {
                ctx.globalAlpha = 0.4 // Other cameras faded
              }

              ctx.drawImage(img, 0, 0, canvas.width, canvas.height)
              ctx.globalAlpha = 1.0

              imagesLoaded++

              // After all images are loaded, redraw grid and points on top
              if (imagesLoaded === totalImages) {
                console.log('🎯 All images loaded, redrawing grid and points on top')
                drawGridOverlay(ctx, canvas.width, canvas.height)
                drawAllCameraBevPoints(canvas)
              }
            }
            img.src = `data:image/jpeg;base64,${result.transformed_image_base64}`
          }
        })
      }
    } else {
      // No calibrated cameras, just draw points on top of grid
      console.log('🎯 No calibrated cameras, drawing points on grid')
      drawAllCameraBevPoints(canvas)
    }
  }, [calibrationResults, selectedCamera, cameraBevPoints, bevPoints])

  // Draw BEV points from all cameras (current camera highlighted, others as reference)
  const drawAllCameraBevPoints = (canvas: HTMLCanvasElement) => {
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    // Draw reference points from other cameras (faded)
    Object.entries(cameraBevPoints).forEach(([cameraIdStr, points]) => {
      const cameraId = parseInt(cameraIdStr)
      if (cameraId !== selectedCamera && points.length > 0) {
        drawReferencePoints(ctx, points, cameraId, canvas.width, canvas.height)
      }
    })

    // Draw current camera's points on top (fully opaque)
    if (bevPoints.length > 0) {
      drawCurrentCameraPoints(ctx, bevPoints, canvas.width, canvas.height)
    }
  }

  // Draw reference points from other cameras
  const drawReferencePoints = (ctx: CanvasRenderingContext2D, points: Point[], cameraId: number, width: number, height: number) => {
    ctx.globalAlpha = 0.4 // Faded for reference

    points.forEach((point, index) => {
      const x = point.x * width
      const y = point.y * height

      // Draw reference point with camera-specific color
      const cameraColors = getCameraColorVariants(cameraId)
      ctx.fillStyle = cameraColors.faded
      ctx.beginPath()
      ctx.arc(x, y, 6, 0, 2 * Math.PI)
      ctx.fill()

      // Draw camera ID as label
      ctx.fillStyle = SYSTEM_COLORS.label
      ctx.font = 'bold 10px Arial'
      ctx.textAlign = 'center'
      ctx.fillText(`C${cameraId}`, x, y + 3)
    })

    ctx.globalAlpha = 1.0 // Reset opacity
  }

  // Draw current camera's points
  const drawCurrentCameraPoints = (ctx: CanvasRenderingContext2D, points: Point[], width: number, height: number) => {
    points.forEach((point, index) => {
      const x = point.x * width
      const y = point.y * height

      // Draw current camera point (bright and numbered)
      ctx.fillStyle = getCalibrationPointColor(index, 1.0)
      ctx.beginPath()
      ctx.arc(x, y, 8, 0, 2 * Math.PI)
      ctx.fill()

      // Draw point number
      ctx.fillStyle = SYSTEM_COLORS.label
      ctx.font = 'bold 12px Arial'
      ctx.textAlign = 'center'
      ctx.fillText((index + 1).toString(), x, y + 4)
    })
  }

  // Helper function to draw grid overlay
  const drawGridOverlay = (ctx: CanvasRenderingContext2D, width: number, height: number) => {
    // Draw grid lines
    ctx.strokeStyle = SYSTEM_COLORS.gridLines
    ctx.lineWidth = 1

    const gridSize = 10
    for (let i = 0; i <= gridSize; i++) {
      const x = (i / gridSize) * width
      const y = (i / gridSize) * height

      // Vertical lines
      ctx.beginPath()
      ctx.moveTo(x, 0)
      ctx.lineTo(x, height)
      ctx.stroke()

      // Horizontal lines
      ctx.beginPath()
      ctx.moveTo(0, y)
      ctx.lineTo(width, y)
      ctx.stroke()
    }

    // Draw center cross
    ctx.strokeStyle = SYSTEM_COLORS.origin
    ctx.lineWidth = 2

    const centerX = width / 2
    const centerY = height / 2

    // Center cross
    ctx.beginPath()
    ctx.moveTo(centerX - 20, centerY)
    ctx.lineTo(centerX + 20, centerY)
    ctx.moveTo(centerX, centerY - 20)
    ctx.lineTo(centerX, centerY + 20)
    ctx.stroke()

    // Draw border
    ctx.strokeStyle = SYSTEM_COLORS.gridLines
    ctx.lineWidth = 2
    ctx.strokeRect(1, 1, width - 2, height - 2)
  }

  // Fetch camera configuration on component mount to detect number of cameras
  useEffect(() => {
    if (configuredCameras.length === 0) {
      console.log('🎯 Fetching camera configuration for calibration UI...')
      dispatch(fetchCameraConfig())
    }
  }, [dispatch, configuredCameras.length])

  // Load existing calibration data on component mount
  useEffect(() => {
    const fetchCalibrationData = async () => {
      try {
        console.log('🎯 Loading existing calibration data...')
        const response = await fetch('/api/calibration/calibration-data')
        if (response.ok) {
          const data = await response.json()
          if (data.success && data.calibration_data) {
            console.log('🎯 Loaded calibration data:', data)
            dispatch(loadCalibrationData({
              calibration_data: data.calibration_data,
              status: data.status
            }))
          } else {
            console.log('🎯 No existing calibration data found')
          }
        }
      } catch (error) {
        console.error('🎯 Failed to load calibration data:', error)
      }
    }
    fetchCalibrationData()
  }, [dispatch])

  // Debug log camera detection
  useEffect(() => {
    console.log('🎯 Calibration UI camera detection:', {
      configuredCameras: configuredCameras.length,
      calibrationMaxCameras,
      finalMaxCameras: maxCameras
    })
  }, [configuredCameras.length, calibrationMaxCameras, maxCameras])

  // Simple initial grid drawing function that doesn't depend on any state
  const drawInitialGrid = (canvas: HTMLCanvasElement) => {
    console.log('🎯 drawInitialGrid called', { canvasWidth: canvas.width, canvasHeight: canvas.height })
    const ctx = canvas.getContext('2d')
    if (!ctx) {
      console.error('🎯 Failed to get canvas context')
      return
    }

    ctx.clearRect(0, 0, canvas.width, canvas.height)

    // Draw grid background
    ctx.fillStyle = SYSTEM_COLORS.canvasBackground
    ctx.fillRect(0, 0, canvas.width, canvas.height)

    // Draw grid overlay (this function is self-contained)
    drawGridOverlay(ctx, canvas.width, canvas.height)

    // Add a small indicator to confirm the canvas is working
    ctx.fillStyle = '#ff0000'
    ctx.fillRect(canvas.width - 20, 10, 10, 10)
    console.log('🎯 Initial grid drawn with red indicator')
  }

  // Initial canvas setup - draw basic grid when component mounts
  useEffect(() => {
    const canvas = bevCanvasRef.current
    if (canvas) {
      // Use requestAnimationFrame to ensure canvas is properly rendered
      requestAnimationFrame(() => {
        drawInitialGrid(canvas)
      })
    }
  }, []) // Empty dependency array - runs once on mount

  // Additional effect to redraw when tab becomes visible
  useEffect(() => {
    const canvas = bevCanvasRef.current
    if (canvas) {
      // Force redraw when any of these dependencies change
      requestAnimationFrame(() => {
        drawBevGrid(canvas)
      })
    }
  }, [calibrationResults, selectedCamera, drawBevGrid])

  // Update canvas drawings when points change
  useEffect(() => {
    if (imageCanvasRef.current && frames) {
      drawPoints(imageCanvasRef.current, imagePoints, true, true)
    }
  }, [imagePoints, frames])

  useEffect(() => {
    if (bevCanvasRef.current) {
      drawBevGrid(bevCanvasRef.current)
    }
  }, [bevPoints, cameraBevPoints, calibrationResult, calibrationResults, selectedCamera, drawBevGrid])

  // Redraw grid specifically when calibration data loads
  useEffect(() => {
    const canvas = bevCanvasRef.current
    if (canvas && Object.keys(calibrationResults).length > 0) {
      console.log('🎯 Redrawing grid after calibration data loaded')
      requestAnimationFrame(() => {
        drawBevGrid(canvas)
      })
    }
  }, [calibrationResults, drawBevGrid])

  // Redraw grid immediately after frames are captured
  useEffect(() => {
    const canvas = bevCanvasRef.current
    if (canvas && frames) {
      console.log('🎯 Frames captured, redrawing grid')
      requestAnimationFrame(() => {
        drawBevGrid(canvas)
      })
    }
  }, [frames, drawBevGrid])

  // Force redraw when calibration is reset (when calibratedCameras becomes empty)
  useEffect(() => {
    const canvas = bevCanvasRef.current
    if (canvas && calibratedCameras.length === 0) {
      console.log('🎯 Calibration reset detected, redrawing grid')
      requestAnimationFrame(() => {
        drawBevGrid(canvas)
      })
    }
  }, [calibratedCameras.length, drawBevGrid])

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold">
            Camera Calibration
            {isCalibrationComplete && (
              <span className="text-[#2da89b] text-lg ml-3">✅ Complete</span>
            )}
          </h2>
          {calibratedCameras.length > 0 && (
            <p className="text-sm text-[#8e8e8e] mt-1">
              Progress: {calibratedCameras.length}/{maxCameras} cameras calibrated
              {isCalibrationComplete && " • System ready for tracking"}
            </p>
          )}
        </div>
        <div className="flex space-x-3">
          <button
            onClick={handleCaptureFrames}
            disabled={loading || !isStreamReady}
            className={`px-4 py-2 rounded text-white transition-colors ${
              isStreamReady
                ? 'bg-gradient-to-r from-[#38bd85] to-[#2da89b] hover:from-[#38bd85]/80 hover:to-[#2da89b]/80 disabled:opacity-50'
                : 'bg-[#8e8e8e] cursor-not-allowed'
            }`}
          >
            {loading ? 'Capturing...' : 'Capture Frames'}
          </button>

          <button
            onClick={handleResetPoints}
            className="px-4 py-2 bg-[#8e8e8e] text-white rounded hover:bg-[#8e8e8e]/80"
          >
            Reset Points
          </button>

          <button
            onClick={handleResetAllCalibration}
            className={`px-4 py-2 rounded text-white transition-colors ${
              isCalibrationComplete
                ? 'bg-[#e9833a] hover:bg-[#e9833a]/80'
                : 'bg-red-600 hover:bg-red-700'
            }`}
          >
            {isCalibrationComplete ? 'Recalibrate All' : 'Reset All'}
          </button>
        </div>
      </div>

      {/* Stream Status Indicator */}
      <div className={`p-4 rounded-lg border-2 ${
        isStreamReady
          ? 'bg-[#212121] border-[#2da89b]/50'
          : 'bg-[#212121] border-[#e9833a]/50'
      }`}>
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className={`w-3 h-3 rounded-full ${isStreamReady ? 'bg-gradient-to-r from-[#38bd85] to-[#2da89b]' : 'bg-[#e9833a]'}`}></div>
            <div>
              <h3 className={`font-medium ${isStreamReady ? 'text-white' : 'text-white'}`}>
                {isStreamReady ? '✅ Video Stream Active' : '⚠️ Video Stream Required'}
              </h3>
              <p className={`text-sm ${isStreamReady ? 'text-white/80' : 'text-white/80'}`}>
                {isStreamReady
                  ? 'Combined video stream is running. You can now capture frames for calibration.'
                  : 'Please start the combined video stream before proceeding with calibration.'
                }
              </p>
            </div>
          </div>

          {!isStreamReady && (
            <button
              onClick={onSwitchToStreams}
              className="px-4 py-2 bg-gradient-to-r from-[#38bd85] to-[#2da89b] text-white rounded hover:from-[#38bd85]/80 hover:to-[#2da89b]/80 transition-colors"
            >
              Go to Live Streams
            </button>
          )}
        </div>
      </div>

      {/* Calibration Completion Status */}
      {isCalibrationComplete && calibrationCompletedAt && (
        <div className="p-6 rounded-lg border-2 bg-[#212121] border-[#2da89b]/50">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-4">
              <CameraIcon className="w-16 h-16" style={{ color: SYSTEM_COLORS.info }} />
              <div>
                <h3 className="text-xl font-bold text-transparent bg-gradient-to-r from-[#38bd85] to-[#2da89b] bg-clip-text">
                  🎉 {maxCameras}-Camera Calibration Complete!
                </h3>
                <p className="text-white/80 mt-1">
                  All {maxCameras} cameras have been successfully calibrated. The system is now ready for accurate tracking.
                </p>
                <p className="text-sm text-[#8e8e8e] mt-2">
                  Completed on {formatCompletionTime(calibrationCompletedAt)}
                </p>
              </div>
            </div>
            <button
              onClick={handleResetAllCalibration}
              className="px-4 py-2 bg-[#e9833a] text-white rounded hover:bg-[#e9833a]/80 transition-colors"
            >
              Recalibrate All
            </button>
          </div>
        </div>
      )}

      {/* Camera Selection */}
      <div className="bg-[#212121] border border-[#8e8e8e]/30 p-4 rounded-lg">
        <h3 className="text-lg font-semibold mb-3">
          Camera Selection ({maxCameras} cameras detected)
          <span className="text-sm text-[#8e8e8e] ml-2">
            • Each camera has individual BEV annotation points
          </span>
        </h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {Array.from({length: maxCameras}, (_, i) => i).map((cameraId) => {
            const isCalibrated = calibratedCameras.includes(cameraId)
            const isSelected = selectedCamera === cameraId
            const cameraBevPointCount = cameraBevPoints[cameraId]?.length || 0
            const currentBevPointCount = isSelected ? bevPoints.length : cameraBevPointCount

            return (
              <button
                key={cameraId}
                onClick={() => handleCameraChange(cameraId as 0 | 1 | 2 | 3)}
                className={`px-6 py-3 rounded-lg border-2 transition-all ${
                  isSelected
                    ? 'border-[#2da89b] bg-gradient-to-r from-[#38bd85] to-[#2da89b] text-white'
                    : 'border-[#8e8e8e]/50 bg-[#212121] text-[#8e8e8e] hover:border-[#8e8e8e]'
                } ${isCalibrated ? 'ring-2 ring-[#2da89b] ring-opacity-50' : ''}`}
              >
                <div className="text-center">
                  <div className="font-medium">
                    Camera {cameraId}
                    {isCalibrated && <span className="ml-2">✅</span>}
                  </div>
                  <div className="text-xs mt-1">
                    {isCalibrated ? (
                      <div className="flex items-center space-x-2">
                        <CheckCircleIcon className="w-5 h-5" style={{ color: SYSTEM_COLORS.success }} />
                        <span style={{ color: SYSTEM_COLORS.success }}>COMPLETE</span>
                      </div>
                    ) : (
                      <span className={`${isSelected ? 'text-white/80' : 'text-[#8e8e8e]'}`}>
                        BEV: {currentBevPointCount}/4 points
                      </span>
                    )}
                  </div>
                </div>
              </button>
            )
          })}
        </div>
      </div>

      {/* Main Calibration Interface */}
      {frames && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Image View */}
          <div className="bg-[#212121] border border-[#8e8e8e]/30 p-4 rounded-lg">
            <h3 className="text-lg font-semibold mb-3">
              Camera {selectedCamera} Image View
              <span className="text-sm text-[#8e8e8e] ml-2">
                ({imagePoints.length}/4 points selected)
              </span>
            </h3>
            <div className="text-center">
              <div className="inline-block relative">
                {(() => {
                  const getCameraFrame = (cameraId: number) => {
                    switch(cameraId) {
                      case 0: return frames.camera0_frame
                      case 1: return frames.camera1_frame
                      case 2: return frames.camera2_frame
                      case 3: return frames.camera3_frame
                      default: return frames.camera0_frame
                    }
                  }

                  const frameData = getCameraFrame(selectedCamera)
                  return frameData ? (
                    <>
                      <img
                        src={`data:image/jpeg;base64,${frameData}`}
                        alt={`Camera ${selectedCamera} frame`}
                        className="block max-w-full h-auto"
                        style={{
                          aspectRatio: `${frames.frame_width}/${frames.frame_height}`,
                          maxWidth: '640px',
                          maxHeight: '480px'
                        }}
                      />
                      <canvas
                        ref={imageCanvasRef}
                        width={frames.frame_width}
                        height={frames.frame_height}
                        onClick={handleImageClick}
                        className="absolute top-0 left-0 w-full h-full cursor-crosshair"
                        style={{ aspectRatio: `${frames.frame_width}/${frames.frame_height}` }}
                      />
                    </>
                  ) : (
                    <div className="w-full h-[480px] bg-[#8e8e8e]/20 flex items-center justify-center rounded">
                      <span className="text-[#8e8e8e]">Camera {selectedCamera} frame not available</span>
                    </div>
                  )
                })()}
              </div>
            </div>
            <p className="text-sm text-[#8e8e8e] mt-2">
              Click to add points on the image. Points will be used to map to BEV coordinates.
              {history.length > 0 && (
                <span className="block text-[#2da89b] mt-1">
                  💡 Tip: Press Ctrl+Z to undo, Ctrl+Shift+Z to redo (Cmd on Mac)
                </span>
              )}
            </p>
          </div>

          {/* BEV View */}
          <div className="bg-[#212121] border border-[#8e8e8e]/30 p-4 rounded-lg">
            <h3 className="text-lg font-semibold mb-3">
              Bird's Eye View Map - Camera {selectedCamera}
              <span className="text-sm text-[#8e8e8e] ml-2">
                ({bevPoints.length}/4 points selected)
              </span>
            </h3>
                          <div className="relative">
                <canvas
                  ref={bevCanvasRef}
                  width={600}
                  height={600}
                  onClick={handleBevClick}
                  className={`border border-[#8e8e8e]/50 mx-auto block ${
                    bevPoints.length >= 4 ? 'cursor-default' : 'cursor-crosshair'
                  }`}
                />
              </div>
              <p className="text-sm text-[#8e8e8e] mt-2">
                Click to add corresponding points for Camera {selectedCamera} on the BEV map. Center represents (300,300) in pixels.
                {Object.keys(cameraBevPoints).length > 0 && (
                  <span className="block mt-1 text-[#2da89b]">
                    💡 Faded points show reference locations from other cameras
                  </span>
                )}
              </p>
          </div>
        </div>
      )}

      {/* Calibration Controls */}
      {frames && (
        <div className="bg-[#212121] border border-[#8e8e8e]/30 p-4 rounded-lg">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-lg font-semibold">Calibration Controls</h3>
              <p className="text-sm text-[#8e8e8e]">
                Select 4 corresponding points on both image and BEV map, then calibrate.
              </p>
            </div>
            <button
              onClick={handlePerformCalibration}
              disabled={isCalibrating || imagePoints.length !== 4 || bevPoints.length !== 4}
              className="px-6 py-3 bg-gradient-to-r from-[#38bd85] to-[#2da89b] text-white rounded-lg hover:from-[#38bd85]/80 hover:to-[#2da89b]/80 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {isCalibrating ? (
                <div className="flex items-center space-x-2">
                  <LoadingSpinner size="sm" />
                  <span>Calibrating...</span>
                </div>
              ) : (
                `Calibrate Camera ${selectedCamera}`
              )}
            </button>
          </div>
        </div>
      )}

      {/* Calibration Results */}
      {calibrationResult && (
        <div className={`p-4 rounded-lg border-2 ${
          calibrationResult.success
            ? 'bg-[#212121] border-[#2da89b]/50'
            : 'bg-[#212121] border-red-500/50'
        }`}>
          <h3 className={`font-semibold ${
            calibrationResult.success ? 'text-white' : 'text-white'
          }`}>
            Camera {selectedCamera} Calibration Result
          </h3>
          <p className={`mt-1 ${
            calibrationResult.success ? 'text-[#2da89b]' : 'text-red-400'
          }`}>
            {calibrationResult.message}
          </p>
        </div>
      )}

      {/* Individual Camera Results */}
      {Object.entries(calibrationResults).map(([cameraIdStr, result]) => {
        const cameraId = parseInt(cameraIdStr)
        if (cameraId === selectedCamera && calibrationResult) return null // Don't duplicate current result

        return (
          <div key={cameraId} className={`p-4 rounded-lg border-2 ${
            result.success
              ? 'bg-[#212121] border-[#2da89b]/50'
              : 'bg-[#212121] border-red-500/50'
          }`}>
            <h3 className={`font-semibold ${
              result.success ? 'text-white' : 'text-white'
            }`}>
              Camera {cameraId} Calibration {result.success ? 'Complete ✅' : 'Failed ❌'}
            </h3>
            <p className={`mt-1 ${
              result.success ? 'text-[#2da89b]' : 'text-red-400'
            }`}>
              {result.success
                ? `Successfully calibrated! ${isCalibrationComplete ? 'Ready for tracking.' : 'Configure other cameras to complete setup.'}`
                : result.message
              }
            </p>
          </div>
        )
      })}
    </div>
  )
}

import { useRef, useEffect } from 'react'
import type { Camera, CombinedStreamState, StreamError } from '../types'
import type { VisionWebSocketService, VisionMetadata } from '../services/VisionWebSocket'
import { useAppDispatch, useAppSelector } from '../store/hooks'
import { setVisionEnabled, setVisionLoading } from '../store/slices/visionSlice'
import { selectCombinedResolution, selectIndividualResolution, selectDisplayScale, selectScaledCombinedResolution, setDisplayScale } from '../store/slices/cameraConfigSlice'
import { setStreamDelays } from '../store/slices/streamSlice'
import { StreamDelayControls } from './StreamDelayControls'
import {
  MagnifyingGlassIcon,
  ChartBarIcon
} from '@heroicons/react/24/outline'
import { MultiStreamVisionOverlay } from './MultiStreamVisionOverlay'
import { FaEye, FaEyeSlash, FaHourglassHalf } from 'react-icons/fa'
import { StreamErrorOverlay, StreamLoadingOverlay } from './shared'

interface LiveStreamsTabProps {
  cameras: Camera[]
  combinedStreamState: CombinedStreamState
  combinedStreamError?: StreamError
  onCombinedStreamToggle: () => Promise<void>
  onRetryCombinedStream: () => Promise<void>
  visionMetadata: VisionMetadata | null
  visionWebSocket: VisionWebSocketService
  visionWebSocketConnected: boolean
}

export function LiveStreamsTab({
  cameras,
  combinedStreamState,
  combinedStreamError,
  onCombinedStreamToggle,
  onRetryCombinedStream,
  visionMetadata,
  visionWebSocket,
}: LiveStreamsTabProps) {
  const dispatch = useAppDispatch()
  const videoRef = useRef<HTMLVideoElement>(null)

  // Redux state selectors
  const isVisionEnabled = useAppSelector(state => state.vision.isEnabled)
  const visionLoading = useAppSelector(state => state.vision.isLoading)
  const combinedResolution = useAppSelector(selectCombinedResolution)
  const individualResolution = useAppSelector(selectIndividualResolution)
  const displayScale = useAppSelector(selectDisplayScale)
  const scaledCombinedResolution = useAppSelector(selectScaledCombinedResolution)


  const baseButtonClass = "mt-4 px-6 py-3 rounded text-sm font-medium transition-colors min-w-[180px]"

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

  const getButtonClass = () => {

    switch (combinedStreamState) {
      case 'connecting':
      case 'negotiating':
      case 'waiting_for_media':
        return `${baseButtonClass} bg-[#e9833a] text-white cursor-not-allowed`
      case 'streaming':
        return `${baseButtonClass} bg-red-600 text-white hover:bg-red-700`
      case 'error':
        return `${baseButtonClass} bg-[#e9833a] text-white hover:bg-[#e9833a]/80`
      case 'disconnected':
      default:
        return `${baseButtonClass} bg-gradient-to-r from-[#38bd85] to-[#2da89b] text-white hover:from-[#38bd85]/80 hover:to-[#2da89b]/80`
    }
  }

  const getStatusText = () => {
    if (combinedStreamState === 'error' && combinedStreamError) {
      return `Error: ${combinedStreamError.message}`
    }

    switch (combinedStreamState) {
      case 'connecting': return 'Connecting...'
      case 'negotiating': return 'Establishing connection...'
      case 'waiting_for_media': return 'Waiting for video frames...'
      case 'streaming': return 'Streaming (Combined)'
      case 'error': return 'Error'
      case 'disconnected':
      default: return 'Disconnected'
    }
  }

  const getStatusColor = () => {
    switch (combinedStreamState) {
      case 'streaming': return 'text-transparent bg-gradient-to-r from-[#38bd85] to-[#2da89b] bg-clip-text'
      case 'connecting':
      case 'negotiating':
      case 'waiting_for_media': return 'text-[#e9833a]'
      case 'error': return 'text-red-400'
      case 'disconnected':
      default: return 'text-[#8e8e8e]'
    }
  }

  const handleButtonClick = async () => {
    if (combinedStreamState === 'error') {
      await onRetryCombinedStream()
    } else {
      await onCombinedStreamToggle()
    }
  }



  const isButtonDisabled = () => {
    return combinedStreamState === 'connecting' ||
           combinedStreamState === 'negotiating' ||
           combinedStreamState === 'waiting_for_media'
  }

  return (
    <div>

      {/* Combined Stream Status */}
      <div className="mb-6 p-4 bg-[#212121] border border-[#8e8e8e]/30 rounded-lg">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-lg font-semibold mb-2">Combined Video Stream</h3>
            <div className={`flex items-center mb-2 ${getStatusColor()}`}>
              <span className="mr-2">●</span>
              <span className="text-sm">{getStatusText()}</span>
            </div>
            <div className="text-xs text-[#8e8e8e]">
              Architecture: Cameras → Stream Combiner → Vision API → WebRTC → React
            </div>
          </div>

          <div className="flex space-x-3">
            <button
              onClick={handleButtonClick}
              disabled={isButtonDisabled()}
              className={getButtonClass()}
            >
              {getButtonText()}
            </button>

            {/* Vision Tracking Toggle */}
            {combinedStreamState === 'streaming' && (
              <button
                onClick={toggleVisionTracking}
                disabled={visionLoading}
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
                {isVisionEnabled ? 'Stop Tracking' : 'Start Tracking'}
              </button>
            )}


          </div>
        </div>

        {combinedStreamError && (
          <div className="mt-2 text-xs text-red-400">
            Error type: {combinedStreamError.type}
          </div>
        )}

        {/* Vision Status */}
        {combinedStreamState === 'streaming' && (
          <div className="mt-3 pt-3 border-t border-[#8e8e8e]/30">
            <div className="flex items-center justify-between">
              <div className="flex items-center">
                                  <span className={`w-2 h-2 rounded-full mr-2 ${isVisionEnabled ? 'bg-gradient-to-r from-[#38bd85] to-[#2da89b]' : 'bg-[#8e8e8e]'}`}></span>
                <span className="text-sm">
                  Vision Tracking: {isVisionEnabled ? 'Active' : 'Inactive'}
                </span>
              </div>
              {visionMetadata && (
                <div className="text-xs text-[#8e8e8e]">
                  Frame {visionMetadata.frame_id} • {visionMetadata.processing_time_ms?.toFixed(1)}ms
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Stream Synchronization Controls */}
      <div className="mb-6 space-y-4">
        <h2 className="text-lg font-semibold">⏱️ Stream Synchronization</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
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
          <p className="text-sm text-gray-500 text-center">
            Start the combined stream to adjust synchronization delays
          </p>
        )}
      </div>

      {/* Display Scale Control */}
      <div className="mb-6 space-y-4">
                  <div className="flex items-center space-x-2">
            <MagnifyingGlassIcon className="w-5 h-5 text-gray-400" />
            <h2 className="text-lg font-semibold">Display Scaling</h2>
          </div>
        <div className="bg-[#212121] border border-[#8e8e8e]/30 p-4 rounded-lg">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-sm font-medium text-[#8e8e8e] mb-1">Video Display Scale</h3>
              <p className="text-xs text-[#8e8e8e]/70">Scales video display size without changing backend resolution</p>
            </div>
            <div className="flex items-center space-x-4">
              <label className="text-sm text-gray-300">Scale: {((displayScale || 1.25) * 100).toFixed(0)}%</label>
              <input
                type="range"
                min="0.5"
                max="2.0"
                step="0.05"
                value={displayScale || 1.25}
                onChange={(e) => dispatch(setDisplayScale(parseFloat(e.target.value)))}
                className="w-32 h-2 bg-gray-700 rounded-lg appearance-none cursor-pointer slider"
              />
              <div className="flex space-x-2">
                <button
                  onClick={() => dispatch(setDisplayScale(1.0))}
                  className="px-2 py-1 text-xs bg-[#8e8e8e] text-white rounded hover:bg-[#8e8e8e]/80"
                >
                  100%
                </button>
                <button
                  onClick={() => dispatch(setDisplayScale(1.25))}
                  className="px-2 py-1 text-xs bg-gradient-to-r from-[#38bd85] to-[#2da89b] text-white rounded hover:from-[#38bd85]/80 hover:to-[#2da89b]/80"
                >
                  125%
                </button>
                <button
                  onClick={() => dispatch(setDisplayScale(1.5))}
                  className="px-2 py-1 text-xs bg-[#e9833a] text-white rounded hover:bg-[#e9833a]/80"
                >
                  150%
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Combined Video Container */}
      <div className="relative max-w-none">
        <div className="relative bg-black rounded-lg overflow-hidden flex justify-center">
          {/* Combined video element at native resolution */}
          <video
            ref={videoRef}
            id="combined-video"
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

          {/* Vision Overlays for multi-stream layout */}
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
                <div className="text-gray-400 text-sm">
                  Native Resolution: {combinedResolution.width}x{combinedResolution.height}
                  ({individualResolution.width}x{individualResolution.height} per camera)
                </div>
                <div className="text-gray-400 text-sm">Click "Start Combined Stream" to begin</div>
              </div>
            </div>
          )}
        </div>

        {/* Camera Labels Overlay - Dynamic Stream Layout */}
        {combinedStreamState === 'streaming' && (
          <div className="absolute inset-0 pointer-events-none">
            {/* Dynamic Camera Labels */}
            {cameras.map((camera, index) => {
              const colors = ['bg-green-400', 'bg-blue-400', 'bg-purple-400', 'bg-orange-400']
              const positions = [
                'top-4 left-4',      // Stream 0: Top-left
                'top-4 right-4',     // Stream 1: Top-right
                'bottom-20 left-4',  // Stream 2: Bottom-left (above stats)
                'bottom-20 right-4'  // Stream 3: Bottom-right (above stats)
              ]

              return (
                <div key={camera.id} className={`absolute ${positions[index] || 'top-4 left-4'} bg-black bg-opacity-75 text-white px-3 py-2 rounded-lg`}>
                  <div className="font-semibold text-sm flex items-center">
                    <span className={`w-2 h-2 ${colors[index] || 'bg-gray-400'} rounded-full mr-2`}></span>
                    📹 {camera.name}
                  </div>
                  <div className="text-xs text-gray-300 mt-1">
                    Stream {camera.id}
                  </div>
                </div>
              )
            })}

            {/* Grid divider lines for multi-stream layouts */}
            {cameras.length > 2 && (
              <>
                {/* Vertical divider */}
                <div className="absolute top-0 bottom-0 left-1/2 w-0.5 bg-white bg-opacity-30 transform -translate-x-0.5"></div>
                {/* Horizontal divider */}
                <div className="absolute left-0 right-0 top-1/2 h-0.5 bg-white bg-opacity-30 transform -translate-y-0.5"></div>
              </>
            )}
            {cameras.length === 2 && (
              /* Single vertical divider for 2-stream layout */
              <div className="absolute top-0 bottom-0 left-1/2 w-0.5 bg-white bg-opacity-30 transform -translate-x-0.5"></div>
            )}
          </div>
        )}
      </div>

      {/* Combined Stream Technical Info */}
      <div className="mt-6">
        <h3 className="text-lg font-semibold mb-4">Stream Information</h3>
        <div className="bg-[#212121] border border-[#8e8e8e]/30 p-4 rounded-lg">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <h4 className="font-medium mb-2 text-transparent bg-gradient-to-r from-[#38bd85] to-[#2da89b] bg-clip-text">📹 Input Sources ({cameras.length} streams)</h4>
              <div className="space-y-1 text-sm text-white/80">
                {cameras.map((camera) => (
                  <div key={camera.id}>
                    • {camera.name}: {camera.stream_url}
                  </div>
                ))}
              </div>
            </div>
            <div>
              <h4 className="font-medium mb-2 text-[#e9833a]">🎬 Output Stream</h4>
              <div className="space-y-1 text-sm text-white/80">
                <div>• Layout: {cameras.length === 1 ? '1x1' : cameras.length === 2 ? '2x1' : '2x2'} grid</div>
                <div>• Resolution: {combinedResolution.width}x{combinedResolution.height}</div>
                <div>• Individual: {individualResolution.width}x{individualResolution.height} per stream</div>
                <div>• Protocol: WebRTC H.264</div>
              </div>
            </div>
          </div>
          {combinedStreamState === 'streaming' && (
            <div className="mt-4 pt-4 border-t border-[#8e8e8e]/30">
                              <div className="flex items-center space-x-2 mb-2">
                  <ChartBarIcon className="w-4 h-4 text-[#38bd85]" />
                  <h4 className="font-medium text-transparent bg-gradient-to-r from-[#38bd85] to-[#2da89b] bg-clip-text">
                    Live Stats
                  </h4>
                </div>
              <div className="grid grid-cols-2 gap-4 text-xs">
                <div>
                  <span className="text-[#8e8e8e]">Combined FPS:</span>
                  <span id="combined-fps" className="font-mono text-transparent bg-gradient-to-r from-[#38bd85] to-[#2da89b] bg-clip-text ml-2">0</span>
                </div>
                <div>
                  <span className="text-[#8e8e8e]">Frame Count:</span>
                  <span id="combined-frames" className="font-mono text-[#e9833a] ml-2">0</span>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

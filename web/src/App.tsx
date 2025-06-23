import { useState, useEffect } from 'react'
import { Navbar } from './components/Navbar'
import { TabNavigation } from './components/TabNavigation'
import { LiveStreamsTab } from './components/LiveStreamsTab'
import { BirdsEyeViewTab } from './components/BirdsEyeViewTab'
import { CalibrationTab } from './components/CalibrationTab'
import { CombinedViewTab } from './components/CombinedViewTab'
import { Footer } from './components/Footer'

import { ToastContainer } from './components/ToastNotification'
import { WebRTCManager } from './services/WebRTCManager'
import { VisionWebSocketService } from './services/VisionWebSocket'
import type { VisionMessage, VisionMetadata } from './services/VisionWebSocket'
import { useAppDispatch, useAppSelector } from './store/hooks'
import { setActiveTab, addToast, removeToast } from './store/slices/uiSlice'
import {
  setCameras,
  setConnectionStatus,
  setCombinedStreamState,
  setCombinedStreamError,
  setStatsPollingInterval,
  updateStreamMetadata,
} from './store/slices/streamSlice'
import {
  setVisionMetadata,
  setWebSocketConnected,
  clearVisionData
} from './store/slices/visionSlice'
import { clearFramesOnDisconnect } from './store/slices/calibrationSlice'
import { fetchCameraConfig } from './store/slices/cameraConfigSlice'

function App() {
  const dispatch = useAppDispatch()

  // Redux state selectors
  const activeTab = useAppSelector(state => state.ui.activeTab)
  const toasts = useAppSelector(state => state.ui.toasts)
  const cameras = useAppSelector(state => state.stream.cameras)
  const connectionStatus = useAppSelector(state => state.stream.connectionStatus)
  const combinedStreamState = useAppSelector(state => state.stream.combinedStreamState)
  const combinedStreamError = useAppSelector(state => state.stream.combinedStreamError)
  const statsPollingInterval = useAppSelector(state => state.stream.statsPollingInterval)
  const visionMetadata = useAppSelector(state => state.vision.visionMetadata)
  const visionWebSocketConnected = useAppSelector(state => state.vision.webSocketConnected)

  // Service instances (these don't need to be in Redux)
  const [webRTCManager] = useState(() => new WebRTCManager())
  const [visionWebSocket] = useState(() => new VisionWebSocketService())

  // Stats polling functions
  const startStatsPolling = () => {
    if (statsPollingInterval) {
      clearInterval(statsPollingInterval)
    }

    const pollStats = async () => {
      try {
        const response = await fetch('/ws/stream-stats')
        const data = await response.json()

        if (data.status === 'success' && data.data) {
          dispatch(updateStreamMetadata({
            fps: data.data.fps,
            frameCount: data.data.frameCount
          }))

          // Update combined stream FPS
          const combinedFpsElement = document.getElementById('combined-fps')
          if (combinedFpsElement) {
            combinedFpsElement.textContent = data.data.fps.toString()
          }

          // Update frame count
          const combinedFramesElement = document.getElementById('combined-frames')
          if (combinedFramesElement) {
            combinedFramesElement.textContent = data.data.frameCount.toString()
          }
        }
      } catch (error) {
        console.error('Failed to fetch stream stats:', error)
      }
    }

    // Poll every 2 seconds
    const interval = setInterval(pollStats, 2000)
    dispatch(setStatsPollingInterval(interval))

    // Initial poll
    pollStats()
  }

  const stopStatsPolling = () => {
    if (statsPollingInterval) {
      clearInterval(statsPollingInterval)
      dispatch(setStatsPollingInterval(null))
    }
  }

  useEffect(() => {
    // Load cameras from API
    loadCameras()

    // Load camera configuration including resolution settings
    dispatch(fetchCameraConfig())

    // Make WebRTC manager available globally for debugging
    ;(window as any).webRTCManager = webRTCManager
    console.log('🔧 WebRTC manager attached to window for debugging')

    // Initialize WebRTC manager
    webRTCManager.onConnectionStatusChange = (status) => {
      dispatch(setConnectionStatus(status))

      // Show connection status toasts
      if (status === 'connected') {
        dispatch(addToast({ message: 'WebSocket connected to server', type: 'success' }))
      } else if (status === 'disconnected') {
        dispatch(addToast({ message: 'Disconnected from server', type: 'warning' }))
      }
    }

    // Combined stream state change handler
    webRTCManager.onCombinedStreamStateChange = (state, error) => {
      console.log(`📊 Combined stream state change: ${state}`, error ? `Error: ${error.message}` : '')

      dispatch(setCombinedStreamState(state))

      if (error) {
        dispatch(setCombinedStreamError(error))
        dispatch(addToast({ message: `Combined stream error: ${error.message}`, type: 'error' }))
      } else {
        // Clear error when state changes to non-error state
        dispatch(setCombinedStreamError(null))

        // Show success toast when streaming starts
        if (state === 'streaming') {
          dispatch(addToast({ message: 'Combined video stream connected successfully', type: 'success' }))
          // Start stats polling when streaming begins
          startStatsPolling()
        }
      }

      // Stop stats polling when stream stops
      if (state === 'disconnected' || state === 'error') {
        stopStatsPolling()
      }
    }

    // Add stream metadata callback for combined stream
    webRTCManager.onStreamMetadata = (metadata) => {
      dispatch(updateStreamMetadata({
        fps: metadata.fps || 0,
        frameCount: metadata.frameCount || 0
      }))

      // Update combined stream FPS
      const combinedFpsElement = document.getElementById('combined-fps')
      if (combinedFpsElement) {
        const fps = metadata.fps || 0
        combinedFpsElement.textContent = fps.toString()
      }

      // Update frame count
      const combinedFramesElement = document.getElementById('combined-frames')
      if (combinedFramesElement) {
        const frames = metadata.frameCount || 0
        combinedFramesElement.textContent = frames.toString()
      }

      // Update individual stream stats in overlays (if they exist) - Dynamic streams
      if (metadata.streams) {
        Object.entries(metadata.streams).forEach(([streamId, streamData]) => {
          const fpsElement = document.getElementById(`fps-${streamId}`)
          if (fpsElement) {
            fpsElement.textContent = (streamData.fps || 0).toString()
          }

          const detectionsElement = document.getElementById(`detections-${streamId}`)
          if (detectionsElement && streamData.detections) {
            detectionsElement.textContent = streamData.detections.length.toString()
          }

          const tracksElement = document.getElementById(`tracks-${streamId}`)
          if (tracksElement && streamData.tracks) {
            tracksElement.textContent = streamData.tracks.length.toString()
          }
        })
      }
    }

    // Set up Vision WebSocket
    visionWebSocket.onMessage = (visionData: VisionMessage) => {
      if ((visionData as any).type === 'vision_metadata') {
        const metadata = visionData as VisionMetadata
        // Calculate total detections and tracks across all streams
        const streamData = Object.entries(metadata.all_streams || {})
        const totalDetections = streamData.reduce((sum, [, data]) => sum + (data as any).detections.length, 0)
        const totalTracks = streamData.reduce((sum, [, data]) => sum + (data as any).tracks.length, 0)

        console.log('📡 App.tsx: Received vision metadata via WebSocket:', {
          frame_id: metadata.frame_id,
          timestamp: metadata.timestamp,
          processing_time: metadata.processing_time_ms,
          num_streams: metadata.num_streams,
          active_stream_ids: metadata.active_stream_ids,
          total_detections: totalDetections,
          total_tracks: totalTracks,
          bev_tracks: metadata.bev_tracks.length,
          stream_details: Object.fromEntries(
            streamData.map(([streamId, data]) => [
              streamId,
              { detections: (data as any).detections.length, tracks: (data as any).tracks.length }
            ])
          )
        })
        dispatch(setVisionMetadata(metadata))
      } else if ((visionData as any).type === 'vision_status') {
        const status = visionData as any
        console.log('📊 App.tsx: Received vision status via WebSocket:', {
          tracking_enabled: status.tracking_enabled,
          active_stream_ids: status.active_stream_ids,
          message: status.message
        })
        // Don't dispatch vision_status to Redux, just log it
      } else {
        console.log('📡 App.tsx: Received unknown vision message type:', (visionData as any).type)
      }
    }

    visionWebSocket.onConnect = () => {
      console.log('📡 App.tsx: Vision WebSocket connected')
      dispatch(setWebSocketConnected(true))
      dispatch(addToast({ message: 'Vision WebSocket connected', type: 'success' }))
    }

    visionWebSocket.onDisconnect = () => {
      console.log('📡 App.tsx: Vision WebSocket disconnected')
      dispatch(setWebSocketConnected(false))
      dispatch(clearVisionData())
      dispatch(clearFramesOnDisconnect())
      dispatch(addToast({ message: 'Vision WebSocket disconnected', type: 'warning' }))
    }

    visionWebSocket.onError = (error) => {
      console.error('📡 App.tsx: Vision WebSocket error:', error)
      dispatch(addToast({ message: 'Vision WebSocket error', type: 'error' }))
    }

    webRTCManager.connect()

    return () => {
      webRTCManager.disconnect()
      visionWebSocket.disconnect()
      stopStatsPolling()
    }
  }, [webRTCManager, dispatch])

  // Handle tab changes - reconnect video element when returning to streams or combined tab
  useEffect(() => {
    if (activeTab === 'streams' || activeTab === 'combined') {
      // Small delay to ensure DOM is ready
      setTimeout(() => {
        reconnectCombinedStream()
      }, 100)
    }
  }, [activeTab])

  const reconnectCombinedStream = () => {
    // Check if combined stream is active and reconnect video element
    if (combinedStreamState === 'streaming' || combinedStreamState === 'waiting_for_media') {
      if (webRTCManager.isCombinedStreamActive()) {
        // Try to reconnect the video element
        const reconnected = webRTCManager.reconnectVideoElement()
        if (reconnected) {
          console.log('🔄 Reconnected combined video element')
        }
      }
    }
  }

  const loadCameras = async () => {
    try {
      const response = await fetch('/api/cameras')
      const data = await response.json()
      dispatch(setCameras(data))
    } catch (error) {
      console.error('Failed to load cameras:', error)
      dispatch(addToast({ message: 'Failed to load camera configuration', type: 'error' }))
    }
  }

  const handleCombinedStreamToggle = async () => {
    const currentState = combinedStreamState

    if (currentState === 'disconnected' || currentState === 'error') {
      // Start combined stream
      try {
        await webRTCManager.startCombinedStream()
      } catch (error) {
        console.error('Failed to start combined stream:', error)
        dispatch(addToast({ message: 'Failed to start combined stream', type: 'error' }))
      }
    } else {
      // Stop combined stream
      webRTCManager.stopCombinedStream()
    }
  }

  const handleRetryCombinedStream = async () => {
    console.log('🔄 Retrying combined stream')
    try {
      await webRTCManager.retryCombinedStream()
    } catch (error) {
      console.error('Failed to retry combined stream:', error)
      dispatch(addToast({ message: 'Failed to retry combined stream', type: 'error' }))
    }
  }

  const handleTabChange = (tab: typeof activeTab) => {
    dispatch(setActiveTab(tab))
  }

  const handleRemoveToast = (id: string) => {
    dispatch(removeToast(id))
  }

  return (
    <div className="min-h-screen bg-[#212121] text-white flex flex-col">
      <Navbar connectionStatus={connectionStatus} />

      {/* Main content area - grows to fill available space */}
      <div className="flex-1 w-4/5 max-w-[2000px] mx-auto px-6 mt-6">
        <TabNavigation
          activeTab={activeTab}
          onTabChange={handleTabChange}
        />

        <div className="mt-6 pb-6">
          {activeTab === 'streams' && (
            <LiveStreamsTab
              cameras={cameras}
              combinedStreamState={combinedStreamState}
              combinedStreamError={combinedStreamError || undefined}
              onCombinedStreamToggle={handleCombinedStreamToggle}
              onRetryCombinedStream={handleRetryCombinedStream}
              visionMetadata={visionMetadata}
              visionWebSocket={visionWebSocket}
              visionWebSocketConnected={visionWebSocketConnected}
            />
          )}

          {activeTab === 'combined' && (
            <CombinedViewTab
              cameras={cameras}
              combinedStreamState={combinedStreamState}
              combinedStreamError={combinedStreamError || undefined}
              onCombinedStreamToggle={handleCombinedStreamToggle}
              onRetryCombinedStream={handleRetryCombinedStream}
              visionMetadata={visionMetadata}
              visionWebSocket={visionWebSocket}
              visionWebSocketConnected={visionWebSocketConnected}
            />
          )}

          {activeTab === 'bev' && (
            <BirdsEyeViewTab />
          )}

          {activeTab === 'calibration' && (
            <CalibrationTab
              combinedStreamState={combinedStreamState}
              onSwitchToStreams={() => dispatch(setActiveTab('streams'))}
            />
          )}
        </div>
      </div>

      {/* Footer - sticks to bottom when content is short, scrolls naturally when content is long */}
      <Footer />

      {/* Toast Notifications */}
      <ToastContainer
        toasts={toasts}
        onRemoveToast={handleRemoveToast}
      />
    </div>
  )
}

export default App

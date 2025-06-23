import React, { useState, useEffect } from 'react'
import type { WebRTCManager } from '../services/WebRTCManager'
import { SYSTEM_COLORS } from '../utils/colors'
import {
  EyeIcon,
  ChartBarIcon,
  MagnifyingGlassIcon
} from '@heroicons/react/24/outline'

interface OverlayControlsProps {
  webRTCManager: WebRTCManager
  className?: string
}

export default function OverlayControls({ webRTCManager, className = '' }: OverlayControlsProps) {
  const [overlayVisible, setOverlayVisible] = useState(true)
  const [showDetections, setShowDetections] = useState(true)
  const [showTracks, setShowTracks] = useState(true)
  const [showConfidence, setShowConfidence] = useState(true)
  const [showIds, setShowIds] = useState(true)
  // Debug options
  const [showCameraBoundaries, setShowCameraBoundaries] = useState(false)
  const [showCoordinateGrid, setShowCoordinateGrid] = useState(false)
  const [showDebugInfo, setShowDebugInfo] = useState(true)
  const [syncStatus, setSyncStatus] = useState<any>(null)

  // Update overlay configuration when settings change
  useEffect(() => {
    webRTCManager.configureOverlay({
      showDetections,
      showTracks,
      showConfidence,
      showIds,
      showCameraBoundaries,
      showCoordinateGrid,
      showDebugInfo
    })
  }, [webRTCManager, showDetections, showTracks, showConfidence, showIds, showCameraBoundaries, showCoordinateGrid, showDebugInfo])

  // Update overlay visibility
  useEffect(() => {
    webRTCManager.toggleOverlay(overlayVisible)
  }, [webRTCManager, overlayVisible])

  // Periodically check sync status
  useEffect(() => {
    const interval = setInterval(() => {
      const status = webRTCManager.getSynchronizationStatus()
      setSyncStatus(status)
    }, 1000)

    return () => clearInterval(interval)
  }, [webRTCManager])

  return (
          <div className={`p-4 rounded-lg shadow-lg ${className}`} style={{ backgroundColor: SYSTEM_COLORS.canvasBackground }}>
        <div className="flex items-center space-x-2 mb-4">
          <EyeIcon className="w-5 h-5" style={{ color: SYSTEM_COLORS.info }} />
          <h3 className="text-lg font-semibold" style={{ color: SYSTEM_COLORS.label }}>
            Vision Overlay Controls
          </h3>
        </div>

      {/* Synchronization Status */}
      <div className="mb-4 p-3 bg-gray-700 rounded">
        <div className="flex items-center space-x-2 mb-2">
          <ChartBarIcon className="w-4 h-4" style={{ color: SYSTEM_COLORS.info }} />
          <h4 className="text-sm font-medium" style={{ color: SYSTEM_COLORS.coordinates }}>
            Sync Status
          </h4>
        </div>
        <div className="grid grid-cols-2 gap-2 text-xs">
          <div className="flex items-center">
            <div className={`w-2 h-2 rounded-full mr-2 ${
              syncStatus?.synchronizerActive ? 'bg-green-400' : 'bg-red-400'
            }`}></div>
            Synchronizer: {syncStatus?.synchronizerActive ? 'Active' : 'Inactive'}
          </div>
          <div className="flex items-center">
            <div className={`w-2 h-2 rounded-full mr-2 ${
              syncStatus?.overlayRendererActive ? 'bg-green-400' : 'bg-red-400'
            }`}></div>
            Renderer: {syncStatus?.overlayRendererActive ? 'Active' : 'Inactive'}
          </div>
          {syncStatus?.bufferStatus && (
            <>
              <div>Video Frames: {syncStatus.bufferStatus.videoFrames}</div>
              <div>Vision Data: {syncStatus.bufferStatus.visionData}</div>
            </>
          )}
        </div>
      </div>

      {/* Overlay Toggle */}
      <div className="mb-4">
        <label className="flex items-center cursor-pointer">
          <input
            type="checkbox"
            checked={overlayVisible}
            onChange={(e) => setOverlayVisible(e.target.checked)}
            className="sr-only"
          />
          <div className={`relative w-11 h-6 rounded-full transition-colors ${
            overlayVisible ? 'bg-blue-600' : 'bg-gray-600'
          }`}>
            <div className={`absolute w-4 h-4 bg-white rounded-full top-1 transition-transform ${
              overlayVisible ? 'translate-x-6' : 'translate-x-1'
            }`}></div>
          </div>
          <span className="ml-3 text-sm font-medium">Show Overlay</span>
        </label>
      </div>

      {/* Overlay Options */}
      {overlayVisible && (
        <div className="space-y-4">
          {/* Vision Data Options */}
          <div>
            <h4 className="text-sm font-medium mb-3">Vision Data</h4>
            <div className="space-y-2 ml-2">
              <label className="flex items-center cursor-pointer">
                <input
                  type="checkbox"
                  checked={showDetections}
                  onChange={(e) => setShowDetections(e.target.checked)}
                  className="w-4 h-4 text-blue-600 bg-gray-700 border-gray-600 rounded focus:ring-blue-500"
                />
                <span className="ml-2 text-sm flex items-center space-x-1">
            <MagnifyingGlassIcon className="w-3 h-3" />
            <span>Show Detections (Red)</span>
          </span>
              </label>

              <label className="flex items-center cursor-pointer">
                <input
                  type="checkbox"
                  checked={showTracks}
                  onChange={(e) => setShowTracks(e.target.checked)}
                  className="w-4 h-4 text-blue-600 bg-gray-700 border-gray-600 rounded focus:ring-blue-500"
                />
                <span className="ml-2 text-sm">🔄 Show Tracks (Teal)</span>
              </label>

              <label className="flex items-center cursor-pointer">
                <input
                  type="checkbox"
                  checked={showConfidence}
                  onChange={(e) => setShowConfidence(e.target.checked)}
                  className="w-4 h-4 text-blue-600 bg-gray-700 border-gray-600 rounded focus:ring-blue-500"
                />
                <span className="ml-2 text-sm flex items-center space-x-1">
            <ChartBarIcon className="w-3 h-3" />
            <span>Show Confidence</span>
          </span>
              </label>

              <label className="flex items-center cursor-pointer">
                <input
                  type="checkbox"
                  checked={showIds}
                  onChange={(e) => setShowIds(e.target.checked)}
                  className="w-4 h-4 text-blue-600 bg-gray-700 border-gray-600 rounded focus:ring-blue-500"
                />
                <span className="ml-2 text-sm">🏷️ Show IDs</span>
              </label>
            </div>
          </div>

          {/* Debug Options */}
          <div>
            <h4 className="text-sm font-medium mb-3">🔧 Debug Tools</h4>
            <div className="space-y-2 ml-2">
              <label className="flex items-center cursor-pointer">
                <input
                  type="checkbox"
                  checked={showCameraBoundaries}
                  onChange={(e) => setShowCameraBoundaries(e.target.checked)}
                  className="w-4 h-4 text-blue-600 bg-gray-700 border-gray-600 rounded focus:ring-blue-500"
                />
                <span className="ml-2 text-sm">📐 Camera Boundaries (Yellow)</span>
              </label>

              <label className="flex items-center cursor-pointer">
                <input
                  type="checkbox"
                  checked={showCoordinateGrid}
                  onChange={(e) => setShowCoordinateGrid(e.target.checked)}
                  className="w-4 h-4 text-blue-600 bg-gray-700 border-gray-600 rounded focus:ring-blue-500"
                />
                <span className="ml-2 text-sm">📏 Coordinate Grid</span>
              </label>

              <label className="flex items-center cursor-pointer">
                <input
                  type="checkbox"
                  checked={showDebugInfo}
                  onChange={(e) => setShowDebugInfo(e.target.checked)}
                  className="w-4 h-4 text-blue-600 bg-gray-700 border-gray-600 rounded focus:ring-blue-500"
                />
                <span className="ml-2 text-sm">🐛 Console Debug Logs</span>
              </label>
            </div>
          </div>
        </div>
      )}

      {/* Performance Info */}
      {syncStatus?.bufferStatus && (
        <div className="mt-4 p-3 bg-gray-700 rounded text-xs">
          <h4 className="text-sm font-medium mb-2">📈 Buffer Status</h4>
          <div className="grid grid-cols-2 gap-2">
            <div>Video Frames: {syncStatus.bufferStatus.videoFrames}</div>
            <div>Vision Data: {syncStatus.bufferStatus.visionData}</div>
            {syncStatus.bufferStatus.oldestVideoFrame && (
              <div>Oldest Video: {syncStatus.bufferStatus.oldestVideoFrame}ms</div>
            )}
            {syncStatus.bufferStatus.oldestVisionData && (
              <div>Oldest Vision: {syncStatus.bufferStatus.oldestVisionData}ms</div>
            )}
          </div>
        </div>
      )}

      <div className="mt-4 text-xs text-gray-400">
        💡 Use debug tools to verify coordinate mapping. Bounding boxes should align with objects in the video.
      </div>
    </div>
  )
}

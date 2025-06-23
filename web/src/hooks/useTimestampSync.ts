/**
 * React hook for timestamp-synchronized vision overlays
 * Helps match vision data with video frames to handle WebRTC latency
 */

import { useRef, useEffect, useCallback, useState } from 'react'
import type { VisionMetadata } from '../services/VisionWebSocket'

interface VideoFrameInfo {
  timestamp: number
  videoCurrentTime: number
  realTime: number
}

interface VisionDataWithAge extends VisionMetadata {
  ageMs: number
}

interface SyncedData {
  videoFrame: VideoFrameInfo
  visionData: VisionMetadata
  timeDiff: number
}

interface SyncStatus {
  videoFrames: number
  visionData: number
  matchesFound: number
  lastSyncTimestamp?: number
}

export function useTimestampSync(
  videoRef: React.RefObject<HTMLVideoElement | null>,
  currentVisionData: VisionMetadata | null
) {
  // Buffers for synchronization
  const videoFrames = useRef<VideoFrameInfo[]>([])
  const visionDataBuffer = useRef<VisionDataWithAge[]>([])
  const frameIntervalRef = useRef<number>(0)

  // State for synchronized data
  const [syncedData, setSyncedData] = useState<SyncedData | null>(null)
  const [syncStatus, setSyncStatus] = useState<SyncStatus>({
    videoFrames: 0,
    visionData: 0,
    matchesFound: 0
  })

  // Configuration - more lenient for real-world latency
  const MAX_BUFFER_SIZE = 30
  const TIMESTAMP_TOLERANCE_MS = 200  // Increased tolerance for WebRTC latency
  const MAX_AGE_MS = 1000  // Keep data longer for delayed matches

  // Helper functions
  const findClosestVisionData = useCallback((videoTimestamp: number): VisionDataWithAge | null => {
    let closest: VisionDataWithAge | null = null
    let minDiff = Infinity

    for (const vision of visionDataBuffer.current) {
      const visionTimestampMs = vision.timestamp * 1000
      const diff = Math.abs(visionTimestampMs - videoTimestamp)

      if (diff < TIMESTAMP_TOLERANCE_MS && diff < minDiff) {
        minDiff = diff
        closest = vision
      }
    }

    return closest
  }, [TIMESTAMP_TOLERANCE_MS])

  const cleanupBuffers = useCallback(() => {
    // Remove old frames
    const cutoff = Date.now() - MAX_AGE_MS
    videoFrames.current = videoFrames.current.filter(frame => frame.realTime > cutoff)
    visionDataBuffer.current = visionDataBuffer.current.filter(vision => vision.ageMs < MAX_AGE_MS)

    // Limit buffer sizes
    if (videoFrames.current.length > MAX_BUFFER_SIZE) {
      videoFrames.current = videoFrames.current.slice(-MAX_BUFFER_SIZE)
    }
    if (visionDataBuffer.current.length > MAX_BUFFER_SIZE) {
      visionDataBuffer.current = visionDataBuffer.current.slice(-MAX_BUFFER_SIZE)
    }
  }, [MAX_BUFFER_SIZE, MAX_AGE_MS])

  // Add video frame timestamp
  const addVideoFrame = useCallback((video: HTMLVideoElement | null): VideoFrameInfo | null => {
    if (!video) return null;
    const now = Date.now()

    // Use performance.now() for more accurate timing
    const frameInfo: VideoFrameInfo = {
      timestamp: now,
      videoCurrentTime: video.currentTime,
      realTime: now
    }

    videoFrames.current.push(frameInfo)

    // Try to find matching vision data
    const matchingVision = findClosestVisionData(frameInfo.timestamp)
    if (matchingVision) {
      const timeDiff = Math.abs(frameInfo.timestamp - (matchingVision.timestamp * 1000))

      setSyncedData({
        videoFrame: frameInfo,
        visionData: matchingVision,
        timeDiff
      })



      setSyncStatus(prev => ({
        ...prev,
        matchesFound: prev.matchesFound + 1,
        lastSyncTimestamp: now
      }))

      // Remove matched vision data from buffer
      const index = visionDataBuffer.current.indexOf(matchingVision)
      if (index > -1) {
        visionDataBuffer.current.splice(index, 1)
      }
    }

    cleanupBuffers()

    setSyncStatus(prev => ({
      ...prev,
      videoFrames: videoFrames.current.length,
      visionData: visionDataBuffer.current.length
    }))

    return frameInfo
  }, [findClosestVisionData, cleanupBuffers])

  // Add vision data
  const addVisionData = useCallback((visionData: VisionMetadata) => {
    const now = Date.now()

    const visionWithAge: VisionDataWithAge = {
      ...visionData,
      ageMs: now - (visionData.timestamp * 1000)
    }

    visionDataBuffer.current.push(visionWithAge)

    // Always update with latest data as fallback
    setSyncedData(prev => ({
      videoFrame: prev?.videoFrame || { timestamp: now, videoCurrentTime: 0, realTime: now },
      visionData: visionData,
      timeDiff: 0
    }))



    cleanupBuffers()

    setSyncStatus(prev => ({
      ...prev,
      visionData: visionDataBuffer.current.length
    }))
  }, [cleanupBuffers])

  // Start frame timestamp capture
  useEffect(() => {
    const video = videoRef.current
    if (!video) return

    // Clear existing interval
    if (frameIntervalRef.current) {
      clearInterval(frameIntervalRef.current)
    }

    // Capture frame timestamps at ~30fps
    frameIntervalRef.current = window.setInterval(() => {
      if (video.readyState >= 2) {
        addVideoFrame(video)
      }
    }, 33)

    return () => {
      if (frameIntervalRef.current) {
        clearInterval(frameIntervalRef.current)
      }
    }
  }, [videoRef, addVideoFrame])

  // Process incoming vision data
  useEffect(() => {
    if (currentVisionData) {
      addVisionData(currentVisionData)
    }
  }, [currentVisionData, addVisionData])

  // Clear buffers on unmount
  useEffect(() => {
    return () => {
      videoFrames.current = []
      visionDataBuffer.current = []
    }
  }, [])

  return {
    syncedData,
    syncStatus,
    clearBuffers: () => {
      videoFrames.current = []
      visionDataBuffer.current = []
      setSyncedData(null)
      setSyncStatus({
        videoFrames: 0,
        visionData: 0,
        matchesFound: 0
      })
    }
  }
}

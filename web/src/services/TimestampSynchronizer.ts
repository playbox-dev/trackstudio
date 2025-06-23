/**
 * Timestamp-based Synchronizer for Video Frames and Vision Data
 * Matches vision metadata to video frames using timestamps for precise overlay sync
 */

import type { VisionMetadata } from './VisionWebSocket'

interface VideoFrameInfo {
  timestamp: number
  videoCurrentTime: number
  realTime: number // Date.now() when frame was captured
}

interface VisionDataWithAge extends VisionMetadata {
  ageMs: number // How old this data is
}

export class TimestampSynchronizer {
  private videoFrames: VideoFrameInfo[] = []
  private visionDataBuffer: VisionDataWithAge[] = []

  // Configuration
  private readonly MAX_BUFFER_SIZE = 30 // Keep last 30 frames/vision data
  private readonly TIMESTAMP_TOLERANCE_MS = 150 // Match within 150ms
  private readonly MAX_AGE_MS = 500 // Discard vision data older than 500ms

  // Callbacks
  public onSyncedData?: (videoFrame: VideoFrameInfo, visionData: VisionMetadata) => void
  public onVideoFrame?: (frameInfo: VideoFrameInfo) => void

  constructor() {
    console.log('🕐 TimestampSynchronizer initialized')
  }

  /**
   * Add a video frame timestamp
   */
  addVideoFrame(videoElement: HTMLVideoElement): VideoFrameInfo {
    const now = Date.now()
    const frameInfo: VideoFrameInfo = {
      timestamp: now,
      videoCurrentTime: videoElement.currentTime,
      realTime: now
    }

    this.videoFrames.push(frameInfo)
    this.cleanupVideoFrames()

    // Try to find matching vision data for this frame
    this.tryMatch(frameInfo)

    // Call video frame callback
    this.onVideoFrame?.(frameInfo)

    return frameInfo
  }

  /**
   * Add vision data with timestamp
   */
  addVisionData(visionData: VisionMetadata): void {
    const now = Date.now()
    const visionWithAge: VisionDataWithAge = {
      ...visionData,
      ageMs: now - (visionData.timestamp * 1000) // Convert to ms and calculate age
    }

    this.visionDataBuffer.push(visionWithAge)
    this.cleanupVisionData()

    // Try to find matching video frame for this vision data
    this.tryMatchVision(visionWithAge)
  }

  /**
   * Try to match a video frame with existing vision data
   */
  private tryMatch(videoFrame: VideoFrameInfo): void {
    const matchingVision = this.findClosestVisionData(videoFrame.timestamp)
    if (matchingVision) {
      console.log('🎯 Frame-Vision sync match found:', {
        videoTimestamp: videoFrame.timestamp,
        visionTimestamp: matchingVision.timestamp * 1000,
        timeDiff: Math.abs(videoFrame.timestamp - (matchingVision.timestamp * 1000)),
        visionAge: matchingVision.ageMs
      })

      this.onSyncedData?.(videoFrame, matchingVision)

      // Remove matched vision data to prevent duplicate matches
      this.removeVisionData(matchingVision)
    }
  }

  /**
   * Try to match vision data with existing video frames
   */
  private tryMatchVision(visionData: VisionDataWithAge): void {
    const visionTimestampMs = visionData.timestamp * 1000
    const matchingFrame = this.findClosestVideoFrame(visionTimestampMs)

    if (matchingFrame) {
      console.log('🎯 Vision-Frame sync match found:', {
        visionTimestamp: visionTimestampMs,
        videoTimestamp: matchingFrame.timestamp,
        timeDiff: Math.abs(visionTimestampMs - matchingFrame.timestamp),
        visionAge: visionData.ageMs
      })

      this.onSyncedData?.(matchingFrame, visionData)

      // Remove matched frame to prevent duplicate matches
      this.removeVideoFrame(matchingFrame)
    }
  }

  /**
   * Find the closest vision data to a given timestamp
   */
  private findClosestVisionData(videoTimestamp: number): VisionDataWithAge | null {
    let closest: VisionDataWithAge | null = null
    let minDiff = Infinity

    for (const vision of this.visionDataBuffer) {
      const visionTimestampMs = vision.timestamp * 1000
      const diff = Math.abs(visionTimestampMs - videoTimestamp)

      if (diff < this.TIMESTAMP_TOLERANCE_MS && diff < minDiff) {
        minDiff = diff
        closest = vision
      }
    }

    return closest
  }

  /**
   * Find the closest video frame to a given timestamp
   */
  private findClosestVideoFrame(visionTimestamp: number): VideoFrameInfo | null {
    let closest: VideoFrameInfo | null = null
    let minDiff = Infinity

    for (const frame of this.videoFrames) {
      const diff = Math.abs(frame.timestamp - visionTimestamp)

      if (diff < this.TIMESTAMP_TOLERANCE_MS && diff < minDiff) {
        minDiff = diff
        closest = frame
      }
    }

    return closest
  }

  /**
   * Remove a specific vision data entry
   */
  private removeVisionData(target: VisionDataWithAge): void {
    const index = this.visionDataBuffer.findIndex(v =>
      v.frame_id === target.frame_id && v.timestamp === target.timestamp
    )
    if (index !== -1) {
      this.visionDataBuffer.splice(index, 1)
    }
  }

  /**
   * Remove a specific video frame entry
   */
  private removeVideoFrame(target: VideoFrameInfo): void {
    const index = this.videoFrames.findIndex(f =>
      f.timestamp === target.timestamp && f.videoCurrentTime === target.videoCurrentTime
    )
    if (index !== -1) {
      this.videoFrames.splice(index, 1)
    }
  }

  /**
   * Clean up old video frames
   */
  private cleanupVideoFrames(): void {
    // Remove frames older than buffer size
    if (this.videoFrames.length > this.MAX_BUFFER_SIZE) {
      this.videoFrames = this.videoFrames.slice(-this.MAX_BUFFER_SIZE)
    }

    // Remove frames older than max age
    const cutoff = Date.now() - this.MAX_AGE_MS
    this.videoFrames = this.videoFrames.filter(frame => frame.realTime > cutoff)
  }

  /**
   * Clean up old vision data
   */
  private cleanupVisionData(): void {
    // Remove data older than buffer size
    if (this.visionDataBuffer.length > this.MAX_BUFFER_SIZE) {
      this.visionDataBuffer = this.visionDataBuffer.slice(-this.MAX_BUFFER_SIZE)
    }

    // Remove data older than max age
    this.visionDataBuffer = this.visionDataBuffer.filter(vision => vision.ageMs < this.MAX_AGE_MS)
  }

  /**
   * Get current buffer status for debugging
   */
  getBufferStatus(): {
    videoFrames: number
    visionData: number
    oldestVideoFrame?: number
    newestVideoFrame?: number
    oldestVisionData?: number
    newestVisionData?: number
  } {
    const now = Date.now()

    return {
      videoFrames: this.videoFrames.length,
      visionData: this.visionDataBuffer.length,
      oldestVideoFrame: this.videoFrames.length > 0 ? now - this.videoFrames[0].realTime : undefined,
      newestVideoFrame: this.videoFrames.length > 0 ? now - this.videoFrames[this.videoFrames.length - 1].realTime : undefined,
      oldestVisionData: this.visionDataBuffer.length > 0 ? this.visionDataBuffer[0].ageMs : undefined,
      newestVisionData: this.visionDataBuffer.length > 0 ? this.visionDataBuffer[this.visionDataBuffer.length - 1].ageMs : undefined
    }
  }

  /**
   * Clear all buffers
   */
  clear(): void {
    this.videoFrames = []
    this.visionDataBuffer = []
    console.log('🧹 TimestampSynchronizer buffers cleared')
  }
}

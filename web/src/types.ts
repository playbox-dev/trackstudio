export interface Camera {
  id: number
  name: string
  stream_url: string  // Generic stream URL (can be RTMP, RTSP, etc.)
  enabled: boolean
  status: string
}

export type ConnectionStatus = 'connected' | 'connecting' | 'disconnected'

// Stream state for the single combined stream
export type CombinedStreamState =
  | 'disconnected'
  | 'connecting'           // WebSocket connecting
  | 'negotiating'          // WebRTC offer/answer exchange
  | 'waiting_for_media'    // Connection established, waiting for video frames
  | 'streaming'            // Actively receiving combined video stream
  | 'error'                // Error state

export interface StreamError {
  type: 'connection' | 'media' | 'timeout' | 'sdp' | 'ice' | 'unknown'
  message: string
  timestamp: number
  retryable: boolean
}

export interface Detection {
  bbox: [number, number, number, number] // [x, y, width, height]
  confidence: number
  class: string
  class_id: number
}

export interface Track {
  track_id: string
  bbox: [number, number, number, number]
  confidence: number
  age: number
  camera_id: number
  global_id?: number  // Global ID for cross-camera tracking
}

export interface BEVTrack {
  track_id: string
  bev_x: number
  bev_y: number
  confidence: number
  global_id?: number  // Global ID for cross-camera tracking
  trajectory?: Array<[number, number, number]>  // Array of [x, y, timestamp] for recent positions
}

export interface StreamMetadata {
  frame_id: number
  timestamp: number
  camera_id?: number  // Optional for combined streams
  detections: Detection[]
  tracks: Track[]
  bev_tracks?: BEVTrack[]
  vision_available: boolean
  fps?: number
  // Combined stream specific fields
  frameCount?: number
  // Dynamic stream data (supports any number of streams)
  streams?: {
    [streamId: string]: {
      fps?: number
      detections?: Detection[]
      tracks?: Track[]
    }
  }
}

export interface CalibrationPoint {
  image_x: number
  image_y: number
  bev_x: number | null
  bev_y: number | null
  index: number
}

// WebRTC message types for combined stream
export interface WebRTCOffer {
  message_type: 'offer'
  type: string
  sdp: string
}

export interface WebRTCAnswer {
  type: 'answer'
  sdp: string
}

export interface WebRTCError {
  type: 'error'
  message: string
  error_type?: 'connection' | 'media' | 'timeout' | 'sdp' | 'ice'
  retryable?: boolean
}

export interface CombinedStreamStartMessage {
  message_type: 'start-combined-stream'
}

export interface CombinedStreamStopMessage {
  message_type: 'stop-combined-stream'
}

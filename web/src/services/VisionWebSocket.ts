 /**
 * Vision WebSocket Service
 * Handles WebSocket connection for receiving vision metadata
 */

export interface StreamData {
  detections: Array<{
    id: number
    bbox: [number, number, number, number]
    confidence: number
    class_name: string
    class_id: number
    center: [number, number]
  }>
  tracks: Array<{
    id: string
    bbox: [number, number, number, number]
    confidence: number
    class_name: string
    center: [number, number]
  }>
}

export interface VisionMetadata {
  type: 'vision_metadata'
  timestamp: number
  frame_id: number
  processing_time_ms: number
  num_streams: number
  active_stream_ids: number[]
  // Multi-stream data
  all_streams: Record<string, StreamData>
  bev_tracks: Array<{
    id: string
    position: [number, number]
    velocity: [number, number]
    confidence: number
    class_name: string
    global_id?: number  // Global ID for cross-camera tracking
    trajectory?: Array<[number, number, number]>  // Array of [x, y, timestamp] for recent positions
  }>
}

export interface VisionStatus {
  type: 'vision_status'
  timestamp: number
  tracking_enabled: boolean
  active_stream_ids: number[]
  message: string
}

export type VisionMessage = VisionMetadata | VisionStatus

export class VisionWebSocketService {
  private websocket: WebSocket | null = null
  private reconnectInterval: number | null = null
  private isConnecting = false
  private shouldReconnect = true

  // Callbacks
  public onMessage?: (data: VisionMessage) => void
  public onConnect?: () => void
  public onDisconnect?: () => void
  public onError?: (error: Event) => void

  // Reconnection settings
  private readonly RECONNECT_DELAY = 3000 // 3 seconds
  private readonly MAX_RECONNECT_ATTEMPTS = 10
  private reconnectAttempts = 0

  constructor() {
    // Vision WebSocket service initialized
  }

  connect(): void {
    if (this.websocket?.readyState === WebSocket.OPEN) {
      return
    }

    if (this.isConnecting) {
      return
    }

    this.isConnecting = true

    try {
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
      const host = window.location.host
      const url = `${protocol}//${host}/ws/vision-metadata`

      this.websocket = new WebSocket(url)

      this.websocket.onopen = () => {
        this.isConnecting = false
        this.reconnectAttempts = 0
        this.onConnect?.()
      }

      this.websocket.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data) as VisionMessage
          this.onMessage?.(data)
        } catch (error) {
          console.error('Error parsing vision metadata:', error)
        }
      }

      this.websocket.onclose = (event) => {
        this.isConnecting = false
        this.websocket = null
        this.onDisconnect?.()

        // Attempt to reconnect if enabled
        if (this.shouldReconnect && this.reconnectAttempts < this.MAX_RECONNECT_ATTEMPTS) {
          this.scheduleReconnect()
        } else if (this.reconnectAttempts >= this.MAX_RECONNECT_ATTEMPTS) {
          console.error('Max reconnection attempts reached for vision WebSocket')
        }
      }

      this.websocket.onerror = (error) => {
        console.error('Vision WebSocket error:', error)
        this.isConnecting = false
        this.onError?.(error)
      }

    } catch (error) {
      console.error('Failed to create vision WebSocket:', error)
      this.isConnecting = false
    }
  }

  disconnect(): void {
    this.shouldReconnect = false

    if (this.reconnectInterval) {
      clearTimeout(this.reconnectInterval)
      this.reconnectInterval = null
    }

    if (this.websocket) {
      this.websocket.close()
      this.websocket = null
    }
  }

  private scheduleReconnect(): void {
    if (this.reconnectInterval) {
      clearTimeout(this.reconnectInterval)
    }

    this.reconnectAttempts++

    this.reconnectInterval = window.setTimeout(() => {
      this.reconnectInterval = null
      if (this.shouldReconnect) {
        this.connect()
      }
    }, this.RECONNECT_DELAY)
  }

  isConnected(): boolean {
    return this.websocket?.readyState === WebSocket.OPEN
  }

  getConnectionState(): string {
    if (!this.websocket) return 'disconnected'

    switch (this.websocket.readyState) {
      case WebSocket.CONNECTING: return 'connecting'
      case WebSocket.OPEN: return 'connected'
      case WebSocket.CLOSING: return 'closing'
      case WebSocket.CLOSED: return 'closed'
      default: return 'unknown'
    }
  }
}

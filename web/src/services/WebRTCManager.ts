import type {
  ConnectionStatus,
  WebRTCOffer,
  WebRTCAnswer,
  WebRTCError,
  StreamMetadata,
  CombinedStreamState,
  StreamError,

  CombinedStreamStopMessage
} from '../types'

import { TimestampSynchronizer } from './TimestampSynchronizer'

interface CombinedStreamInfo {
  pc: RTCPeerConnection
  state: CombinedStreamState
  error?: StreamError
  lastFrameTime?: number
  frameCount: number
  retryCount: number
  dataChannel?: RTCDataChannel
}

export class WebRTCManager {
  private websocket: WebSocket | null = null
  private combinedStream: CombinedStreamInfo | null = null
  private connectionTimeout?: number
  private frameCheckInterval?: number

  // New synchronization components
  private timestampSynchronizer?: TimestampSynchronizer
  private frameTimestampInterval?: number

  public onConnectionStatusChange?: (status: ConnectionStatus) => void
  public onStreamMetadata?: (metadata: StreamMetadata) => void
  public onCombinedStreamStateChange?: (state: CombinedStreamState, error?: StreamError) => void
  public onVisionMetadata?: (visionData: any) => void

  // Constants for timeouts and retry logic
  private readonly CONNECTION_TIMEOUT = 15000 // 15 seconds
  private readonly FRAME_TIMEOUT = 10000 // 10 seconds to receive first frame
  private readonly MAX_RETRY_ATTEMPTS = 3
  private readonly FRAME_CHECK_INTERVAL = 1000 // Check for frames every second

  // Public method to check if combined stream is active
  isCombinedStreamActive(): boolean {
    return this.combinedStream !== null && this.combinedStream.state !== 'disconnected'
  }

  // Public method to get combined stream state
  getCombinedStreamState(): CombinedStreamState {
    return this.combinedStream?.state || 'disconnected'
  }

  // Public method to get combined stream error
  getCombinedStreamError(): StreamError | undefined {
    return this.combinedStream?.error
  }

  // Debug method to check data channel status
  debugDataChannelStatus() {
    console.log('📡 🔍 MANUAL DATA CHANNEL DEBUG:')
    if (this.combinedStream?.dataChannel) {
      console.log('✅ Data channel exists:', {
        readyState: this.combinedStream.dataChannel.readyState,
        bufferedAmount: this.combinedStream.dataChannel.bufferedAmount,
        id: this.combinedStream.dataChannel.id,
        label: this.combinedStream.dataChannel.label,
        ordered: this.combinedStream.dataChannel.ordered
      })
      console.log('📊 Peer connection state:', {
        connectionState: this.combinedStream.pc.connectionState,
        iceConnectionState: this.combinedStream.pc.iceConnectionState,
        iceGatheringState: this.combinedStream.pc.iceGatheringState,
        signalingState: this.combinedStream.pc.signalingState
      })
    } else {
      console.log('❌ No data channel found')
    }
  }

  // Public method to reconnect video element to existing stream
  reconnectVideoElement(): boolean {
    if (!this.combinedStream) {
      return false
    }

    // Try to find any available video element (streams tab or combined tab)
    const video = document.getElementById('combined-video') as HTMLVideoElement ||
                 document.getElementById('combined-video-main') as HTMLVideoElement

    if (!video) {
      console.log('🔄 No video element found for reconnection')
      return false
    }

    // Check if there are already tracks and try to reattach
    this.combinedStream.pc.getReceivers().forEach(receiver => {
      if (receiver.track && receiver.track.kind === 'video') {
        console.log('🔄 Reconnecting combined video track to:', video.id)
        const stream = new MediaStream([receiver.track])
        video.srcObject = stream

        // Set up frame detection for reconnected video
        this.setupFrameDetection(video)
      }
    })

    return true
  }

  connect() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const wsUrl = `${protocol}//${window.location.host}/ws/webrtc`

    this.websocket = new WebSocket(wsUrl)

    this.websocket.onopen = () => {
      console.log('📡 WebSocket connected')
      this.onConnectionStatusChange?.('connected')
    }

    this.websocket.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data)
        const messageType = message.type || message.message_type

        // Only log non-keepalive messages to reduce console noise
        if (messageType !== 'ping' && messageType !== 'pong') {
          console.log('📡 WebSocket message received:', messageType)
        }

        this.handleWebSocketMessage(message)
      } catch (error) {
        console.error('Error parsing WebSocket message:', error)
      }
    }

    this.websocket.onclose = (event) => {
      console.log('📡 WebSocket disconnected:', event.code, event.reason)
      this.onConnectionStatusChange?.('disconnected')

      // Mark combined stream as disconnected
      if (this.combinedStream) {
        this.updateCombinedStreamState('error', {
          type: 'connection',
          message: `WebSocket disconnected (${event.code}: ${event.reason || 'Unknown'})`,
          timestamp: Date.now(),
          retryable: true
        })
      }

      // Reconnect after 3 seconds if not intentionally closed
      if (event.code !== 1000 && event.code !== 1001) {
        setTimeout(() => this.connect(), 3000)
      }
    }

    this.websocket.onerror = (error) => {
      console.error('📡 WebSocket error:', error)
      this.onConnectionStatusChange?.('disconnected')
    }
  }

  disconnect() {
    if (this.websocket) {
      this.websocket.close()
      this.websocket = null
    }

    // Clean up combined stream
    this.cleanupCombinedStream()
  }

  async startCombinedStream(): Promise<void> {
    try {
      console.log('🎥 Starting combined stream')

      // Check if stream already exists
      if (this.combinedStream) {
        const currentState = this.combinedStream.state
        if (currentState !== 'error' && currentState !== 'disconnected') {
          console.warn(`⚠️ Combined stream already exists in state ${currentState}`)
          return
        }
        // Clean up existing stream if in error state
        this.cleanupCombinedStream()
      }

      // Update state to connecting
      this.updateCombinedStreamState('connecting')

      // Ensure WebSocket is connected
      if (!this.websocket || this.websocket.readyState !== WebSocket.OPEN) {
        console.log('⏳ Waiting for WebSocket connection...')
        await this.waitForWebSocket()
      }

      // Set connection timeout
      this.connectionTimeout = window.setTimeout(() => {
        this.handleStreamTimeout('Connection timeout')
      }, this.CONNECTION_TIMEOUT)

      // Create RTCPeerConnection
      const pc = new RTCPeerConnection({
        iceServers: [
          { urls: 'stun:stun.l.google.com:19302' },
          { urls: 'stun:stun1.l.google.com:19302' }
        ]
      })

      // Create data channel BEFORE creating offer (frontend is the offerer)
      console.log('📡 🎯 Creating data channel on frontend (offerer side)...')
      const dataChannel = pc.createDataChannel('vision_metadata', {
        ordered: true,
        protocol: ''
      })
      console.log('📡 🎯 Data channel created on frontend:', {
        id: dataChannel.id,
        label: dataChannel.label,
        readyState: dataChannel.readyState,
        ordered: dataChannel.ordered
      })

      // Set up data channel event handlers
      dataChannel.onopen = () => {
        console.log('📡 ✅ Data channel OPENED on frontend:', {
          readyState: dataChannel.readyState,
          bufferedAmount: dataChannel.bufferedAmount,
          id: dataChannel.id,
          label: dataChannel.label
        })
        console.log('📡 🎉 FRONTEND DATA CHANNEL IS NOW READY TO RECEIVE!')
      }

      dataChannel.onclose = () => {
        console.log('📡 ❌ Data channel CLOSED on frontend')
      }

      dataChannel.onerror = (error) => {
        console.error('📡 ❌ Data channel ERROR on frontend:', error)
      }

      dataChannel.onmessage = (e) => {
        try {
          const data = JSON.parse(e.data)
          console.log('📡 Frontend data channel message received:', {
            type: data.type,
            messageSize: e.data.length,
            keys: Object.keys(data),
            channelState: dataChannel.readyState,
            fullData: data
          })

          if (data.type === 'vision_metadata') {
            // Handle vision metadata
            this.handleVisionMetadata(data)
          } else {
            // Legacy metadata handling
            console.log('📊 Legacy metadata received via frontend channel:', data)
            this.onStreamMetadata?.(data)
          }
        } catch (error) {
          console.error('❌ Error parsing frontend data channel message:', error, 'Raw data:', e.data)
        }
      }

      console.log('📡 Data channel created on frontend:', {
        readyState: dataChannel.readyState,
        id: dataChannel.id,
        label: dataChannel.label
      })

      // Store stream info
      this.combinedStream = {
        pc,
        state: 'connecting',
        frameCount: 0,
        retryCount: 0,
        dataChannel // Store reference to data channel
      }

      // Debug: Log data channel state every 5 seconds
      const debugInterval = setInterval(() => {
        if (this.combinedStream?.dataChannel) {
          console.log('📡 🔍 Frontend data channel status:', {
            readyState: this.combinedStream.dataChannel.readyState,
            bufferedAmount: this.combinedStream.dataChannel.bufferedAmount,
            pcState: this.combinedStream.pc.connectionState,
            iceState: this.combinedStream.pc.iceConnectionState
          })
        } else {
          console.log('📡 🔍 No data channel found on frontend')
        }
      }, 5000)

      // Store interval reference for cleanup
      ;(this.combinedStream as any).debugInterval = debugInterval

      // Set up event handlers
      this.setupPeerConnectionHandlers(pc)

      // Create and send offer
      await this.createAndSendOffer(pc)

    } catch (error) {
      console.error('❌ Failed to start combined stream:', error)
      this.updateCombinedStreamState('error', {
        type: 'unknown',
        message: error instanceof Error ? error.message : 'Unknown error',
        timestamp: Date.now(),
        retryable: true
      })
      this.cleanupCombinedStream()
    }
  }

  stopCombinedStream() {
    console.log('🛑 Stopping combined stream')

    // Send stop message to server
    if (this.websocket && this.websocket.readyState === WebSocket.OPEN) {
      const stopMessage: CombinedStreamStopMessage = {
        message_type: 'stop-combined-stream'
      }
      this.websocket.send(JSON.stringify(stopMessage))
    }

    this.cleanupCombinedStream()
    this.updateCombinedStreamState('disconnected')
  }

  // Retry a failed combined stream
  async retryCombinedStream(): Promise<void> {
    if (!this.combinedStream || this.combinedStream.retryCount >= this.MAX_RETRY_ATTEMPTS) {
      console.log('❌ Max retry attempts reached for combined stream')
      return
    }

    console.log(`🔄 Retrying combined stream (attempt ${this.combinedStream.retryCount + 1})`)
    this.combinedStream.retryCount++

    // Clean up current connection
    this.cleanupCombinedStream(false) // Don't clear the stream object

    // Wait a bit before retrying
    await new Promise(resolve => setTimeout(resolve, 2000))

    // Restart stream
    await this.startCombinedStream()
  }

  private setupPeerConnectionHandlers(pc: RTCPeerConnection) {
    // Handle incoming tracks
    pc.ontrack = (event) => {
      console.log('📹 Received combined video track')
      const video = document.getElementById('combined-video') as HTMLVideoElement ||
                   document.getElementById('combined-video-main') as HTMLVideoElement
      if (video && event.streams && event.streams[0]) {
        video.srcObject = event.streams[0]
        this.updateCombinedStreamState('waiting_for_media')

        // Set up frame detection
        this.setupFrameDetection(video)
      }
    }

    // Handle connection state changes
    pc.onconnectionstatechange = () => {
      console.log(`🔗 Combined stream connection state: ${pc.connectionState}`, {
        connectionState: pc.connectionState,
        iceConnectionState: pc.iceConnectionState,
        iceGatheringState: pc.iceGatheringState,
        signalingState: pc.signalingState
      })

      if (pc.connectionState === 'failed' || pc.connectionState === 'disconnected') {
        this.updateCombinedStreamState('error', {
          type: 'connection',
          message: `WebRTC connection ${pc.connectionState}`,
          timestamp: Date.now(),
          retryable: true
        })
      } else if (pc.connectionState === 'connected') {
        console.log('🔗 ✅ WebRTC connection established successfully!')
        // Clear connection timeout
        if (this.connectionTimeout) {
          clearTimeout(this.connectionTimeout)
          this.connectionTimeout = undefined
        }
      }
    }

    // Handle ICE connection state changes
    pc.oniceconnectionstatechange = () => {
      console.log(`🧊 Combined stream ICE connection state: ${pc.iceConnectionState}`, {
        iceConnectionState: pc.iceConnectionState,
        connectionState: pc.connectionState
      })

      if (pc.iceConnectionState === 'failed') {
        this.updateCombinedStreamState('error', {
          type: 'connection',
          message: 'ICE connection failed',
          timestamp: Date.now(),
          retryable: true
        })
      } else if (pc.iceConnectionState === 'connected' || pc.iceConnectionState === 'completed') {
        console.log('🧊 ✅ ICE connection established!')
      }
    }

    // Handle ICE gathering state changes
    pc.onicegatheringstatechange = () => {
      console.log(`🧊 ICE gathering state: ${pc.iceGatheringState}`)
    }

    // Handle signaling state changes
    pc.onsignalingstatechange = () => {
      console.log(`📶 Signaling state: ${pc.signalingState}`)
    }

    // Note: Data channel is now created by frontend above (not received from server)
  }

  private setupFrameDetection(video: HTMLVideoElement) {
    // Clear any existing frame check interval
    if (this.frameCheckInterval) {
      clearInterval(this.frameCheckInterval)
    }

    // Clear any existing timestamp interval
    if (this.frameTimestampInterval) {
      clearInterval(this.frameTimestampInterval)
    }

    let framesReceived = false

    // Initialize synchronization components
    this.initializeSynchronization(video)

    // Set up multiple detection methods for WebRTC streams

    // Method 1: loadedmetadata event - fires when video metadata is loaded
    const onLoadedMetadata = () => {
      console.log('📹 Video metadata loaded:', video.videoWidth, 'x', video.videoHeight)
      if (video.videoWidth > 0 && video.videoHeight > 0) {
        this.combinedStream!.lastFrameTime = Date.now()
        // Reinitialize timestamp synchronization with correct video dimensions
        this.initializeSynchronization(video)
      }
    }

    // Method 2: loadeddata event - fires when first frame is loaded
    const onLoadedData = () => {
      console.log('📹 Video first frame loaded')
      this.combinedStream!.lastFrameTime = Date.now()
      if (!framesReceived) {
        framesReceived = true
        this.updateCombinedStreamState('streaming')
        console.log('✅ Combined video frames received (loadeddata)')

        // Start frame timestamp capture
        this.startFrameTimestampCapture(video)
      }
    }

    // Method 3: canplay event - fires when video can start playing
    const onCanPlay = () => {
      console.log('📹 Video can play')
      this.combinedStream!.lastFrameTime = Date.now()
      if (!framesReceived) {
        framesReceived = true
        this.updateCombinedStreamState('streaming')
        console.log('✅ Combined video frames received (canplay)')

        // Start frame timestamp capture
        this.startFrameTimestampCapture(video)
      }
    }

    // Method 4: timeupdate event - fires when playback position changes
    const onTimeUpdate = () => {
      if (!framesReceived && video.currentTime > 0) {
        framesReceived = true
        this.updateCombinedStreamState('streaming')
        console.log('✅ Combined video frames received (timeupdate)')

        // Start frame timestamp capture
        this.startFrameTimestampCapture(video)
      }
      this.combinedStream!.lastFrameTime = Date.now()
      this.combinedStream!.frameCount++
    }

    // Add event listeners
    video.addEventListener('loadedmetadata', onLoadedMetadata)
    video.addEventListener('loadeddata', onLoadedData)
    video.addEventListener('canplay', onCanPlay)
    video.addEventListener('timeupdate', onTimeUpdate)

    // Method 5: Manual check for video dimensions (fallback)
    const checkFrames = () => {
      if (!this.combinedStream) return

      // Check if video has valid dimensions (indicates frames are being received)
      if (video.videoWidth > 0 && video.videoHeight > 0) {
        this.combinedStream.lastFrameTime = Date.now()

        if (!framesReceived) {
          framesReceived = true
          this.updateCombinedStreamState('streaming')
          console.log('✅ Combined video frames received (manual check)')

          // Start frame timestamp capture
          this.startFrameTimestampCapture(video)
        }
      }

      // Auto-play video if it's paused (WebRTC streams should play automatically)
      if (video.paused) {
        video.play().catch(e => console.log('Video autoplay prevented:', e))
      }
    }

    // Start frame checking with reduced interval
    this.frameCheckInterval = window.setInterval(checkFrames, this.FRAME_CHECK_INTERVAL) // Check every second

    // Increase timeout for initial frame receipt (WebRTC can take longer)
    setTimeout(() => {
      if (this.combinedStream && !framesReceived && this.combinedStream.state === 'waiting_for_media') {
        console.warn('⚠️ No frames detected within timeout, but WebRTC connection might still be working')
        // Don't immediately fail - WebRTC might still be negotiating
        // this.updateCombinedStreamState('error', {
        //   type: 'media',
        //   message: 'No frames received within timeout period',
        //   timestamp: Date.now(),
        //   retryable: true
        // })
      }
    }, this.FRAME_TIMEOUT)

    // Store cleanup function for later use
    const cleanup = () => {
      video.removeEventListener('loadedmetadata', onLoadedMetadata)
      video.removeEventListener('loadeddata', onLoadedData)
      video.removeEventListener('canplay', onCanPlay)
      video.removeEventListener('timeupdate', onTimeUpdate)

      // Cleanup synchronization components
      this.cleanupSynchronization()
    }

    // Store cleanup in a property that we can access later
    ;(video as any)._webrtcCleanup = cleanup
  }

  /**
   * Initialize synchronization components
   */
  private initializeSynchronization(video: HTMLVideoElement): void {
    try {
      // Cleanup existing components
      this.cleanupSynchronization()

      // Initialize timestamp synchronizer
      this.timestampSynchronizer = new TimestampSynchronizer()

      // Note: Synchronized rendering is now handled by VisionOverlay component
      // using the useTimestampSync hook. The data flows directly to React components.

      console.log('🎯 Timestamp synchronization initialized')

    } catch (error) {
      console.error('❌ Failed to initialize synchronization components:', error)
    }
  }

  /**
   * Start capturing video frame timestamps
   */
  private startFrameTimestampCapture(video: HTMLVideoElement): void {
    if (this.frameTimestampInterval) {
      clearInterval(this.frameTimestampInterval)
    }

    // Capture frame timestamps at ~30fps (every 33ms)
    this.frameTimestampInterval = window.setInterval(() => {
      if (this.timestampSynchronizer && video.readyState >= 2) { // HAVE_CURRENT_DATA
        this.timestampSynchronizer.addVideoFrame(video)
      }
    }, 33) // ~30fps

    console.log('📹 Started frame timestamp capture')
  }

  /**
   * Stop capturing video frame timestamps
   */
  private stopFrameTimestampCapture(): void {
    if (this.frameTimestampInterval) {
      clearInterval(this.frameTimestampInterval)
      this.frameTimestampInterval = undefined
      console.log('📹 Stopped frame timestamp capture')
    }
  }

  /**
   * Cleanup synchronization components
   */
  private cleanupSynchronization(): void {
    // Stop timestamp capture
    this.stopFrameTimestampCapture()

    // Cleanup timestamp synchronizer
    if (this.timestampSynchronizer) {
      this.timestampSynchronizer.clear()
      this.timestampSynchronizer = undefined
    }

    console.log('🧹 Synchronization components cleaned up')
  }

  private async createAndSendOffer(pc: RTCPeerConnection) {
    this.updateCombinedStreamState('negotiating')

    // Create offer
    const offer = await pc.createOffer({
      offerToReceiveAudio: false,
      offerToReceiveVideo: true
    })

    await pc.setLocalDescription(offer)

    // Send offer via WebSocket
    const offerMessage: WebRTCOffer = {
      message_type: 'offer',
      type: pc.localDescription!.type,
      sdp: pc.localDescription!.sdp
    }

    console.log('📤 Sending offer for combined stream')
    this.websocket!.send(JSON.stringify(offerMessage))
  }

  private handleStreamTimeout(message: string) {
    console.error(`⏰ Timeout for combined stream: ${message}`)
    this.updateCombinedStreamState('error', {
      type: 'timeout',
      message,
      timestamp: Date.now(),
      retryable: true
    })
    this.cleanupCombinedStream()
  }

  private updateCombinedStreamState(state: CombinedStreamState, error?: StreamError) {
    if (this.combinedStream) {
      this.combinedStream.state = state
      this.combinedStream.error = error
    }
    this.onCombinedStreamStateChange?.(state, error)
  }

  private cleanupCombinedStream(clearStreamObject: boolean = true) {
    // Clear timeouts
    if (this.connectionTimeout) {
      clearTimeout(this.connectionTimeout)
      this.connectionTimeout = undefined
    }

    if (this.frameCheckInterval) {
      clearInterval(this.frameCheckInterval)
      this.frameCheckInterval = undefined
    }

    // Clear debug interval
    if (this.combinedStream && (this.combinedStream as any).debugInterval) {
      clearInterval((this.combinedStream as any).debugInterval)
    }

    // Cleanup synchronization components
    this.cleanupSynchronization()

    // Close peer connection
    if (this.combinedStream) {
      this.combinedStream.pc.close()
      if (clearStreamObject) {
        this.combinedStream = null
      }
    }

    // Clear video and cleanup event listeners
    const video = document.getElementById('combined-video') as HTMLVideoElement ||
                 document.getElementById('combined-video-main') as HTMLVideoElement
    if (video) {
      // Call stored cleanup function if it exists
      if ((video as any)._webrtcCleanup) {
        (video as any)._webrtcCleanup()
        delete (video as any)._webrtcCleanup
      }
      video.srcObject = null
    }
  }

  private async waitForWebSocket(): Promise<void> {
    return new Promise((resolve, reject) => {
      if (this.websocket && this.websocket.readyState === WebSocket.OPEN) {
        resolve()
        return
      }

      const timeout = setTimeout(() => {
        reject(new Error('WebSocket connection timeout'))
      }, 5000)

      const checkConnection = () => {
        if (this.websocket && this.websocket.readyState === WebSocket.OPEN) {
          clearTimeout(timeout)
          resolve()
        } else if (this.websocket && this.websocket.readyState === WebSocket.CLOSED) {
          clearTimeout(timeout)
          reject(new Error('WebSocket connection failed'))
        } else {
          setTimeout(checkConnection, 100)
        }
      }

      checkConnection()
    })
  }

  private handleWebSocketMessage(message: any) {
    const messageType = message.type || message.message_type
    console.log('📨 Received WebSocket message:', messageType)

    if (messageType === 'answer') {
      this.handleWebRTCAnswer(message)
    } else if (messageType === 'error') {
      this.updateCombinedStreamState('error', {
        type: message.error_type || 'unknown',
        message: message.message,
        timestamp: Date.now(),
        retryable: message.retryable ?? true
      })
      console.error('❌ WebRTC server error:', message.message)
    } else if (messageType === 'connection_established') {
      console.log('✅ WebSocket connection confirmed by server:', message.connection_id)
    } else if (messageType === 'ping') {
      // Respond to server ping immediately and silently
      if (this.websocket && this.websocket.readyState === WebSocket.OPEN) {
        this.websocket.send(JSON.stringify({ type: 'pong' }))
      }
    } else if (messageType === 'pong') {
      // Silently acknowledge pong
    } else {
      console.warn('⚠️ Unknown WebSocket message type:', messageType, message)
    }
  }

  private async handleWebRTCAnswer(message: WebRTCAnswer) {
    if (!this.combinedStream) {
      console.warn('⚠️ Received answer but no combined stream connection exists')
      return
    }

    const pc = this.combinedStream.pc

    // Check peer connection state
    console.log(`📋 Combined stream RTCPeerConnection state: ${pc.signalingState}`)

    if (pc.signalingState !== 'have-local-offer') {
      console.warn(`⚠️ Cannot set remote answer, peer connection state is: ${pc.signalingState}`)
      return
    }

    try {
      console.log('📥 Setting remote description for combined stream')
      await pc.setRemoteDescription(new RTCSessionDescription({
        type: 'answer',
        sdp: message.sdp
      }))
      console.log('✅ Remote description set successfully for combined stream')
    } catch (error) {
      console.error('❌ Failed to set remote description for combined stream:', error)

      this.updateCombinedStreamState('error', {
        type: 'connection',
        message: error instanceof Error ? error.message : 'Failed to set remote description',
        timestamp: Date.now(),
        retryable: true
      })

      this.cleanupCombinedStream()
    }
  }

  private handleVisionMetadata(visionData: any) {
    /**
     * Handle vision metadata received from WebRTC data channel
     */

    // Calculate total detections and tracks across all streams
    const streamData = Object.entries(visionData.all_streams || {})
    const totalDetections = streamData.reduce((sum, [, data]: [string, any]) => sum + (data.detections?.length || 0), 0)
    const totalTracks = streamData.reduce((sum, [, data]: [string, any]) => sum + (data.tracks?.length || 0), 0)

    console.log('🔍 Processing vision metadata:', {
      frame_id: visionData.frame_id,
      timestamp: visionData.timestamp,
      processing_time: visionData.processing_time_ms,
      num_streams: visionData.num_streams,
      active_stream_ids: visionData.active_stream_ids,
      total_detections: totalDetections,
      total_tracks: totalTracks,
      bev_tracks: visionData.bev_tracks?.length || 0,
      stream_details: Object.fromEntries(
        streamData.map(([streamId, data]: [string, any]) => [
          streamId,
          { detections: data.detections?.length || 0, tracks: data.tracks?.length || 0 }
        ])
      )
    })

    // Feed vision data to timestamp synchronizer for matching
    if (this.timestampSynchronizer) {
      this.timestampSynchronizer.addVisionData(visionData)
    }

    // Log detailed detection/track data if present
    streamData.forEach(([streamId, data]: [string, any]) => {
      if (data.detections?.length > 0) {
        console.log(`📹 Stream ${streamId} detections sample:`, data.detections[0])
      }
      if (data.tracks?.length > 0) {
        console.log(`🔄 Stream ${streamId} tracks sample:`, data.tracks[0])
      }
    })

    if (visionData.bev_tracks?.length > 0) {
      console.log('🗺️ BEV tracks sample:', visionData.bev_tracks[0])
    }

    // Call the vision metadata callback if set
    console.log('📤 Calling onVisionMetadata callback with data')
    this.onVisionMetadata?.(visionData)

    // Create metadata using multi-stream format
    const allDetections = streamData.flatMap(([, data]: [string, any]) => data.detections || [])
    const allTracks = streamData.flatMap(([, data]: [string, any]) => data.tracks || [])

    const metadata: StreamMetadata = {
      frame_id: visionData.frame_id,
      timestamp: visionData.timestamp,
      detections: allDetections,
      tracks: allTracks,
      bev_tracks: visionData.bev_tracks || [],
      vision_available: true,
      fps: 0, // Will be calculated separately
      frameCount: visionData.frame_id,
      streams: Object.fromEntries(
        streamData.map(([streamId, data]: [string, any]) => [
          streamId,
          {
            fps: 0,
            detections: data.detections || [],
            tracks: data.tracks || []
          }
        ])
      )
    }

    console.log('📊 Metadata created:', {
      total_detections: metadata.detections.length,
      total_tracks: metadata.tracks.length,
      bev_tracks: metadata.bev_tracks?.length || 0,
      streams_count: Object.keys(metadata.streams || {}).length
    })

    this.onStreamMetadata?.(metadata)
  }

  /**
   * Get synchronization status for debugging
   */
  getSynchronizationStatus(): {
    synchronizerActive: boolean
    bufferStatus?: any
  } {
    return {
      synchronizerActive: !!this.timestampSynchronizer,
      bufferStatus: this.timestampSynchronizer?.getBufferStatus()
    }
  }

  /**
   * Note: Overlay configuration is now handled by VisionOverlay component directly
   */
}

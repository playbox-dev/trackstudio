import { createSlice, type PayloadAction } from '@reduxjs/toolkit'
import type { CombinedStreamState, StreamError, ConnectionStatus, Camera } from '../../types'

interface StreamDelays {
  [streamId: string]: number
}

interface StreamState {
  cameras: Camera[]
  connectionStatus: ConnectionStatus
  combinedStreamState: CombinedStreamState
  combinedStreamError: StreamError | null
  statsPollingInterval: ReturnType<typeof setInterval> | null
  streamDelays: StreamDelays
  streamMetadata: {
    fps: number
    frameCount: number
  }
}

const initialState: StreamState = {
  cameras: [],
  connectionStatus: 'disconnected',
  combinedStreamState: 'disconnected',
  combinedStreamError: null,
  statsPollingInterval: null,
  streamDelays: { '0': 0, '1': 0 },
  streamMetadata: {
    fps: 0,
    frameCount: 0,
  },
}

const streamSlice = createSlice({
  name: 'stream',
  initialState,
  reducers: {
    setCameras: (state, action: PayloadAction<Camera[]>) => {
      state.cameras = action.payload
    },
    setConnectionStatus: (state, action: PayloadAction<ConnectionStatus>) => {
      state.connectionStatus = action.payload
    },
    setCombinedStreamState: (state, action: PayloadAction<CombinedStreamState>) => {
      state.combinedStreamState = action.payload
    },
    setCombinedStreamError: (state, action: PayloadAction<StreamError | null>) => {
      state.combinedStreamError = action.payload
    },
    setStatsPollingInterval: (state, action: PayloadAction<ReturnType<typeof setInterval> | null>) => {
      state.statsPollingInterval = action.payload
    },
    setStreamDelays: (state, action: PayloadAction<StreamDelays>) => {
      state.streamDelays = action.payload
    },
    setStreamDelay: (state, action: PayloadAction<{ streamId: string; delay: number }>) => {
      state.streamDelays[action.payload.streamId] = action.payload.delay
    },
    updateStreamMetadata: (state, action: PayloadAction<Partial<StreamState['streamMetadata']>>) => {
      state.streamMetadata = { ...state.streamMetadata, ...action.payload }
    },
    clearStreamError: (state) => {
      state.combinedStreamError = null
    },
    resetStreamState: (state) => {
      state.combinedStreamState = 'disconnected'
      state.combinedStreamError = null
      state.streamMetadata = {
        fps: 0,
        frameCount: 0,
      }
    },
  },
})

export const {
  setCameras,
  setConnectionStatus,
  setCombinedStreamState,
  setCombinedStreamError,
  setStatsPollingInterval,
  setStreamDelays,
  setStreamDelay,
  updateStreamMetadata,
  clearStreamError,
  resetStreamState,
} = streamSlice.actions

export default streamSlice.reducer

// Selectors
export const selectStreamDelays = (state: { stream: StreamState }) => state.stream.streamDelays
export const selectStreamDelay = (streamId: string) => (state: { stream: StreamState }) =>
  state.stream.streamDelays[streamId] || 0

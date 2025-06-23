import { createSlice, type PayloadAction } from '@reduxjs/toolkit'
import type { VisionMetadata } from '../../services/VisionWebSocket'

interface VisionState {
  visionMetadata: VisionMetadata | null
  webSocketConnected: boolean
  isEnabled: boolean
  isLoading: boolean
  lastFrameId: number | null
  lastUpdateTime: number | null
}

const initialState: VisionState = {
  visionMetadata: null,
  webSocketConnected: false,
  isEnabled: false,
  isLoading: false,
  lastFrameId: null,
  lastUpdateTime: null,
}

const visionSlice = createSlice({
  name: 'vision',
  initialState,
  reducers: {
    setVisionMetadata: (state, action: PayloadAction<VisionMetadata>) => {
      state.visionMetadata = action.payload
      state.lastFrameId = action.payload.frame_id
      state.lastUpdateTime = Date.now()
    },
    setWebSocketConnected: (state, action: PayloadAction<boolean>) => {
      state.webSocketConnected = action.payload
      if (!action.payload) {
        // Clear vision metadata when disconnected
        state.visionMetadata = null
        state.lastFrameId = null
      }
    },
    setVisionEnabled: (state, action: PayloadAction<boolean>) => {
      state.isEnabled = action.payload
    },
    setVisionLoading: (state, action: PayloadAction<boolean>) => {
      state.isLoading = action.payload
    },
    clearVisionData: (state) => {
      state.visionMetadata = null
      state.lastFrameId = null
      state.lastUpdateTime = null
    },
  },
})

export const {
  setVisionMetadata,
  setWebSocketConnected,
  setVisionEnabled,
  setVisionLoading,
  clearVisionData,
} = visionSlice.actions

export default visionSlice.reducer

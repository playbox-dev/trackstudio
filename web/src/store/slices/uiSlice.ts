import { createSlice, type PayloadAction } from '@reduxjs/toolkit'
import type { RootState } from '../index'

type TabType = 'streams' | 'bev' | 'calibration' | 'combined'

interface Toast {
  id: string
  message: string
  type: 'success' | 'error' | 'warning' | 'info'
  timestamp: number
}

interface UIState {
  activeTab: TabType
  toasts: Toast[]
  showAllCameras: boolean
}

const initialState: UIState = {
  activeTab: 'streams',
  toasts: [],
  showAllCameras: true,
}

const uiSlice = createSlice({
  name: 'ui',
  initialState,
  reducers: {
    setActiveTab: (state, action: PayloadAction<TabType>) => {
      state.activeTab = action.payload
    },
    addToast: (state, action: PayloadAction<Omit<Toast, 'id' | 'timestamp'>>) => {
      const toast: Toast = {
        ...action.payload,
        id: `toast-${Date.now()}-${Math.random()}`,
        timestamp: Date.now(),
      }
      state.toasts.push(toast)
    },
    removeToast: (state, action: PayloadAction<string>) => {
      state.toasts = state.toasts.filter(toast => toast.id !== action.payload)
    },
    clearAllToasts: (state) => {
      state.toasts = []
    },
    setShowAllCameras: (state, action: PayloadAction<boolean>) => {
      state.showAllCameras = action.payload
    },
  },
})

export const {
  setActiveTab,
  addToast,
  removeToast,
  clearAllToasts,
  setShowAllCameras,
} = uiSlice.actions

// Selectors
export const selectShowAllCameras = (state: RootState) => state.ui.showAllCameras

export default uiSlice.reducer

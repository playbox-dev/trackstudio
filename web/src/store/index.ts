import { configureStore } from '@reduxjs/toolkit'
import visionSlice from './slices/visionSlice'
import streamSlice from './slices/streamSlice'
import calibrationSlice from './slices/calibrationSlice'
import uiSlice from './slices/uiSlice'
import cameraConfigSlice from './slices/cameraConfigSlice'

export const store = configureStore({
  reducer: {
    vision: visionSlice,
    stream: streamSlice,
    calibration: calibrationSlice,
    ui: uiSlice,
    cameraConfig: cameraConfigSlice,
  },
  middleware: (getDefaultMiddleware) =>
    getDefaultMiddleware({
      serializableCheck: {
        // Ignore these action types
        ignoredActions: ['vision/setVisionMetadata'],
        // Ignore these field paths in all actions
        ignoredActionsPaths: ['meta.arg', 'payload.timestamp'],
        // Ignore these paths in the state
        ignoredPaths: ['vision.visionMetadata.timestamp'],
      },
    }),
})

export type RootState = ReturnType<typeof store.getState>
export type AppDispatch = typeof store.dispatch

import { createSlice, type PayloadAction } from '@reduxjs/toolkit'

interface Point {
  x: number
  y: number
}

interface CalibrationResult {
  success: boolean
  message: string
  transformed_image_base64?: string
  homography_matrix?: number[][]
}

interface CameraFrames {
  camera0_frame?: string
  camera1_frame?: string
  camera2_frame?: string
  camera3_frame?: string
  frame_width: number
  frame_height: number
  num_cameras: number
}

interface UndoItem {
  type: 'image' | 'bev'
  point: Point
  camera: number
}

interface CalibrationState {
  frames: CameraFrames | null
  loading: boolean
  selectedCamera: 0 | 1 | 2 | 3
  isCalibrating: boolean
  imagePoints: Point[]
  bevPoints: Point[]  // Current camera's BEV points
  cameraBevPoints: Record<number, Point[]>  // Per-camera BEV points
  cameraImagePoints: Record<number, Point[]>  // Per-camera image points
  calibrationResult: CalibrationResult | null
  // Multi-camera calibration state
  calibratedCameras: number[]
  calibrationResults: Record<number, CalibrationResult>
  bevPointsLocked: boolean  // Keep for backward compatibility, but will be deprecated
  calibrationCompletedAt: string | null // ISO string
  maxCameras: number // Dynamic based on current setup
  history: UndoItem[] // History of all actions
  historyIndex: number // Current position in history (-1 means at the end)
}

const initialState: CalibrationState = {
  frames: null,
  loading: false,
  selectedCamera: 0,
  isCalibrating: false,
  imagePoints: [],
  bevPoints: [],
  cameraBevPoints: {},  // Per-camera BEV points storage
  cameraImagePoints: {},  // Per-camera image points storage
  calibrationResult: null,
  calibratedCameras: [],
  calibrationResults: {},
  bevPointsLocked: false,
  calibrationCompletedAt: null,
  maxCameras: 2, // Default to 2, will be updated when frames are captured
  history: [], // Initialize history
  historyIndex: -1, // -1 means we're at the end of history
}

const calibrationSlice = createSlice({
  name: 'calibration',
  initialState,
  reducers: {
    setFrames: (state, action: PayloadAction<CameraFrames | null>) => {
      state.frames = action.payload
      if (action.payload) {
        state.maxCameras = action.payload.num_cameras
        // Reset selected camera if it's beyond the available cameras
        if (state.selectedCamera >= action.payload.num_cameras) {
          state.selectedCamera = 0
        }
      }
    },
    setLoading: (state, action: PayloadAction<boolean>) => {
      state.loading = action.payload
    },
    setSelectedCamera: (state, action: PayloadAction<0 | 1 | 2 | 3>) => {
      // Save current camera's points before switching
      if (state.imagePoints.length > 0) {
        state.cameraImagePoints[state.selectedCamera] = [...state.imagePoints]
      }
      if (state.bevPoints.length > 0) {
        state.cameraBevPoints[state.selectedCamera] = [...state.bevPoints]
      }

      // Load points for the new camera
      state.selectedCamera = action.payload
      state.imagePoints = state.cameraImagePoints[action.payload] || []
      state.bevPoints = state.cameraBevPoints[action.payload] || []
    },
    setIsCalibrating: (state, action: PayloadAction<boolean>) => {
      state.isCalibrating = action.payload
    },
    setImagePoints: (state, action: PayloadAction<Point[]>) => {
      state.imagePoints = action.payload
      // Also update the per-camera storage
      state.cameraImagePoints[state.selectedCamera] = [...action.payload]
    },
    addImagePoint: (state, action: PayloadAction<Point>) => {
      if (state.imagePoints.length < 4) {
        state.imagePoints.push(action.payload)
        // Also update the per-camera storage
        state.cameraImagePoints[state.selectedCamera] = [...state.imagePoints]
      }
    },
    setBevPoints: (state, action: PayloadAction<Point[]>) => {
      // Always allow setting BEV points for individual cameras
      state.bevPoints = action.payload
      // Also update the per-camera storage
      state.cameraBevPoints[state.selectedCamera] = [...action.payload]
    },
    addBevPoint: (state, action: PayloadAction<Point>) => {
      if (state.bevPoints.length < 4) {
        state.bevPoints.push(action.payload)
        // Also update the per-camera storage
        state.cameraBevPoints[state.selectedCamera] = [...state.bevPoints]
      }
    },
    setCalibrationResult: (state, action: PayloadAction<CalibrationResult | null>) => {
      state.calibrationResult = action.payload

      if (action.payload?.success) {
        // Mark camera as calibrated
        if (!state.calibratedCameras.includes(state.selectedCamera)) {
          state.calibratedCameras.push(state.selectedCamera)
        }
        // Store the result
        state.calibrationResults[state.selectedCamera] = action.payload

        // Save current camera's BEV points to per-camera storage
        if (state.bevPoints.length === 4) {
          state.cameraBevPoints[state.selectedCamera] = [...state.bevPoints]
        }

        // Check if all cameras are now calibrated
        if (state.calibratedCameras.length === state.maxCameras) {
          state.calibrationCompletedAt = new Date().toISOString()
        }
      }
    },
    addToHistory: (state, action: PayloadAction<UndoItem>) => {
      // If we're not at the end of history, remove everything after current position
      if (state.historyIndex !== -1) {
        state.history = state.history.slice(0, state.historyIndex + 1)
      }

      // Add new action to history
      state.history.push(action.payload)
      state.historyIndex = -1 // Reset to end of history
    },
    undo: (state) => {
      // Determine the effective index
      const currentIndex = state.historyIndex === -1 ? state.history.length - 1 : state.historyIndex

      if (currentIndex < 0) return // Nothing to undo

      const actionToUndo = state.history[currentIndex]

      // If the camera changed since the action, switch back
      if (actionToUndo.camera !== state.selectedCamera) {
        // Save current camera's points before switching
        if (state.imagePoints.length > 0) {
          state.cameraImagePoints[state.selectedCamera] = [...state.imagePoints]
        }
        if (state.bevPoints.length > 0) {
          state.cameraBevPoints[state.selectedCamera] = [...state.bevPoints]
        }

        // Switch to the camera where the undo action happened
        state.selectedCamera = actionToUndo.camera as 0 | 1 | 2 | 3

        // Load the points for that camera
        state.imagePoints = state.cameraImagePoints[actionToUndo.camera] || []
        state.bevPoints = state.cameraBevPoints[actionToUndo.camera] || []
      }

      // Remove the point of the appropriate type
      if (actionToUndo.type === 'image') {
        // Find and remove the specific point
        const index = state.imagePoints.findIndex(p => p.x === actionToUndo.point.x && p.y === actionToUndo.point.y)
        if (index !== -1) {
          state.imagePoints.splice(index, 1)
          // Update the stored points for this camera
          state.cameraImagePoints[actionToUndo.camera] = [...state.imagePoints]
        }
      } else if (actionToUndo.type === 'bev') {
        // Find and remove the specific point
        const index = state.bevPoints.findIndex(p => p.x === actionToUndo.point.x && p.y === actionToUndo.point.y)
        if (index !== -1) {
          state.bevPoints.splice(index, 1)
          // Update the stored points for this camera
          state.cameraBevPoints[actionToUndo.camera] = [...state.bevPoints]
        }
      }

      // Update history index
      state.historyIndex = currentIndex - 1
    },
    redo: (state) => {
      // Calculate the next index
      const nextIndex = state.historyIndex === -1 ? 0 : state.historyIndex + 1

      // Can't redo if we're already at the end
      if (nextIndex >= state.history.length) return

      // Get the action to redo
      const actionToRedo = state.history[nextIndex]

      // If the camera changed, switch to it
      if (actionToRedo.camera !== state.selectedCamera) {
        // Save current camera's points before switching
        if (state.imagePoints.length > 0) {
          state.cameraImagePoints[state.selectedCamera] = [...state.imagePoints]
        }
        if (state.bevPoints.length > 0) {
          state.cameraBevPoints[state.selectedCamera] = [...state.bevPoints]
        }

        // Switch to the camera where the redo action should happen
        state.selectedCamera = actionToRedo.camera as 0 | 1 | 2 | 3

        // Load the points for that camera
        state.imagePoints = state.cameraImagePoints[actionToRedo.camera] || []
        state.bevPoints = state.cameraBevPoints[actionToRedo.camera] || []
      }

      // Re-add the point
      if (actionToRedo.type === 'image' && state.imagePoints.length < 4) {
        state.imagePoints.push(actionToRedo.point)
        // Update the stored points for this camera
        state.cameraImagePoints[actionToRedo.camera] = [...state.imagePoints]
      } else if (actionToRedo.type === 'bev' && state.bevPoints.length < 4) {
        state.bevPoints.push(actionToRedo.point)
        // Update the stored points for this camera
        state.cameraBevPoints[actionToRedo.camera] = [...state.bevPoints]
      }

      // Update history index
      state.historyIndex = nextIndex === state.history.length - 1 ? -1 : nextIndex
    },
    resetPoints: (state) => {
      state.imagePoints = []
      state.bevPoints = []
      state.history = [] // Clear history when resetting
      state.historyIndex = -1
      // Clear current camera's points from per-camera storage
      delete state.cameraBevPoints[state.selectedCamera]
      delete state.cameraImagePoints[state.selectedCamera]
      state.calibrationResult = null
    },
    resetAllCalibration: (state) => {
      state.imagePoints = []
      state.bevPoints = []
      state.cameraBevPoints = {}  // Clear all per-camera BEV points
      state.cameraImagePoints = {}  // Clear all per-camera image points
      state.calibrationResult = null
      state.calibratedCameras = []
      state.calibrationResults = {}
      state.bevPointsLocked = false
      state.calibrationCompletedAt = null
      state.history = [] // Clear history
      state.historyIndex = -1
    },
    loadCalibrationData: (state, action: PayloadAction<{calibration_data: Record<string, any>, status: Record<string, any>}>) => {
      const { calibration_data, status } = action.payload

      // Clear existing state
      state.calibratedCameras = []
      state.calibrationResults = {}
      state.cameraBevPoints = {}
      state.cameraImagePoints = {}

      // Load calibration data for each camera
      Object.entries(calibration_data).forEach(([cameraKey, cameraData]: [string, any]) => {
        if (cameraKey.startsWith('camera')) {
          const cameraId = parseInt(cameraKey.replace('camera', ''))

          // Mark camera as calibrated
          if (!state.calibratedCameras.includes(cameraId)) {
            state.calibratedCameras.push(cameraId)
          }

          // Store BEV and image points
          if (cameraData.bev_points) {
            state.cameraBevPoints[cameraId] = cameraData.bev_points.map((point: [number, number]) => ({
              x: point[0],
              y: point[1]
            }))
          }

          if (cameraData.image_points) {
            state.cameraImagePoints[cameraId] = cameraData.image_points.map((point: [number, number]) => ({
              x: point[0],
              y: point[1]
            }))
          }

          // Create a calibration result
          state.calibrationResults[cameraId] = {
            success: true,
            message: 'Calibration loaded from saved data',
            // Don't include transformed_image_base64 as it's not saved in persistent data
          }
        }
      })

      // Load points for current camera if available
      if (state.cameraBevPoints[state.selectedCamera]) {
        state.bevPoints = [...state.cameraBevPoints[state.selectedCamera]]
      }
      if (state.cameraImagePoints[state.selectedCamera]) {
        state.imagePoints = [...state.cameraImagePoints[state.selectedCamera]]
      }

      // Set completion time if all cameras are calibrated and we have status info
      if (state.calibratedCameras.length === state.maxCameras) {
        // Find the latest calibration time from status
        let latestTime = ''
        Object.entries(status).forEach(([, cameraStatus]: [string, any]) => {
          if (cameraStatus.calibrated && cameraStatus.calibrated_at) {
            if (!latestTime || new Date(cameraStatus.calibrated_at) > new Date(latestTime)) {
              latestTime = cameraStatus.calibrated_at
            }
          }
        })
        if (latestTime) {
          state.calibrationCompletedAt = latestTime
        }
      }
    },
    clearFramesOnDisconnect: (state) => {
      state.frames = null
      state.imagePoints = []
      // Keep per-camera BEV points on disconnect (they're still valuable)
      state.calibrationResult = null
      // Clear history on disconnect
      state.history = []
      state.historyIndex = -1
    },
  },
})

export const {
  setFrames,
  setLoading,
  setSelectedCamera,
  setIsCalibrating,
  setImagePoints,
  addImagePoint,
  setBevPoints,
  addBevPoint,
  setCalibrationResult,
  resetPoints,
  resetAllCalibration,
  loadCalibrationData,
  clearFramesOnDisconnect,
  addToHistory,
  undo,
  redo,
} = calibrationSlice.actions

export default calibrationSlice.reducer

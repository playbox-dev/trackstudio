import { createSlice, createAsyncThunk, type PayloadAction } from '@reduxjs/toolkit'

interface CameraResolution {
  individual_width: number
  individual_height: number
  combined_width: number
  combined_height: number
  fps: number
  display_scale: number  // Global scale factor for display (e.g., 1.25 = 25% larger)
}

interface CameraConfig {
  id: number
  name: string
  stream_url: string
  enabled: boolean
  resolution: {
    width: number
    height: number
    fps: number
  }
}

interface CameraConfigState {
  resolution: CameraResolution
  cameras: CameraConfig[]
  loading: boolean
  error: string | null
  lastFetched: number | null
}

const initialState: CameraConfigState = {
  resolution: {
    individual_width: 720,
    individual_height: 480,
    combined_width: 1440,
    combined_height: 480,
    fps: 15,
    display_scale: 1.25  // Default 25% larger for better viewing
  },
  cameras: [],
  loading: false,
  error: null,
  lastFetched: null
}

// Async thunk to fetch camera configuration
export const fetchCameraConfig = createAsyncThunk(
  'cameraConfig/fetchConfig',
  async (_, { rejectWithValue }) => {
    try {
      const response = await fetch('/api/cameras/config')
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }
      const data = await response.json()
      return data
    } catch (error) {
      return rejectWithValue(error instanceof Error ? error.message : 'Failed to fetch camera config')
    }
  }
)

const cameraConfigSlice = createSlice({
  name: 'cameraConfig',
  initialState,
  reducers: {
    clearError: (state) => {
      state.error = null
    },
    updateResolution: (state, action: PayloadAction<Partial<CameraResolution>>) => {
      state.resolution = { ...state.resolution, ...action.payload }
    },
    setDisplayScale: (state, action: PayloadAction<number>) => {
      state.resolution.display_scale = action.payload
    }
  },
  extraReducers: (builder) => {
    builder
      .addCase(fetchCameraConfig.pending, (state) => {
        state.loading = true
        state.error = null
      })
      .addCase(fetchCameraConfig.fulfilled, (state, action) => {
        state.loading = false
        state.error = null
        state.resolution = action.payload.resolution
        state.cameras = action.payload.cameras
        state.lastFetched = Date.now()
      })
      .addCase(fetchCameraConfig.rejected, (state, action) => {
        state.loading = false
        state.error = action.payload as string
      })
  }
})

export const { clearError, updateResolution, setDisplayScale } = cameraConfigSlice.actions
export default cameraConfigSlice.reducer

// Selectors
export const selectCameraConfig = (state: { cameraConfig: CameraConfigState }) => state.cameraConfig
export const selectCameraResolution = (state: { cameraConfig: CameraConfigState }) => state.cameraConfig.resolution
export const selectIndividualResolution = (state: { cameraConfig: CameraConfigState }) => ({
  width: state.cameraConfig.resolution.individual_width,
  height: state.cameraConfig.resolution.individual_height
})
// Dynamic combined resolution based on number of cameras
export const selectCombinedResolution = (state: { cameraConfig: CameraConfigState }) => {
  const numCameras = state.cameraConfig.cameras.length || 2 // Default to 2 if not loaded yet
  const individualWidth = state.cameraConfig.resolution.individual_width
  const individualHeight = state.cameraConfig.resolution.individual_height

  // Calculate grid layout
  let gridCols, gridRows
  if (numCameras === 1) {
    gridCols = 1; gridRows = 1
  } else if (numCameras === 2) {
    gridCols = 2; gridRows = 1
  } else if (numCameras <= 4) {
    gridCols = 2; gridRows = 2
  } else {
    gridCols = 2; gridRows = 2 // Default
  }

  return {
    width: individualWidth * gridCols,
    height: individualHeight * gridRows
  }
}

export const selectDisplayScale = (state: { cameraConfig: CameraConfigState }) =>
  state.cameraConfig.resolution.display_scale || 1.25

export const selectScaledCombinedResolution = (state: { cameraConfig: CameraConfigState }) => {
  const combinedRes = selectCombinedResolution(state)
  const scale = selectDisplayScale(state) || 1.25
  return {
    width: Math.round(combinedRes.width * scale),
    height: Math.round(combinedRes.height * scale)
  }
}

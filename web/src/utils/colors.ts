/**
 * Centralized Color Scheme for Vision Tracking System
 * Ensures consistent colors across all components
 */

export interface ColorTheme {
  primary: string
  secondary: string
  accent: string
  background: string
}

/**
 * Generate consistent camera-specific colors
 * Each camera gets a distinct hue with consistent saturation/lightness
 */
export const getCameraColor = (cameraId: number, alpha: number = 1.0): string => {
  const hue = (cameraId * 60) % 360 // 0°, 60°, 120°, 180°, 240°, 300°
  return `hsla(${hue}, 75%, 65%, ${alpha})`
}

/**
 * Generate camera colors for different UI states
 */
export const getCameraColorVariants = (cameraId: number) => {
  const hue = (cameraId * 60) % 360
  return {
    normal: `hsla(${hue}, 75%, 65%, 0.8)`,
    bright: `hsla(${hue}, 80%, 70%, 1.0)`,
    faded: `hsla(${hue}, 60%, 55%, 0.4)`,
    selected: `hsla(${hue}, 85%, 75%, 1.0)`,
    background: `hsla(${hue}, 30%, 25%, 0.1)`
  }
}

/**
 * Generate track colors using golden angle for good distribution
 * Consistent across all tracking components
 */
export const getTrackColor = (trackIndex: number, globalId?: number, alpha: number = 1.0): string => {
  // Use global ID for consistent colors across cameras, fallback to index
  const baseValue = globalId !== undefined && globalId !== null ? globalId : trackIndex
  const hue = (baseValue * 137.5) % 360 // Golden angle for optimal distribution
  return `hsla(${hue}, 70%, 60%, ${alpha})`
}

/**
 * Generate track color variants for different states
 */
export const getTrackColorVariants = (trackIndex: number, globalId?: number) => {
  const baseValue = globalId !== undefined && globalId !== null ? globalId : trackIndex
  const hue = (baseValue * 137.5) % 360
  return {
    fill: `hsla(${hue}, 70%, 60%, 1.0)`,
    stroke: `hsla(${hue}, 70%, 40%, 1.0)`,
    selected: '#ffffff',
    faded: `hsla(${hue}, 50%, 50%, 0.6)`,
    trail: `hsla(${hue}, 70%, 50%, 0.8)`
  }
}

/**
 * Generate calibration point colors (numbered points 1-4)
 */
export const getCalibrationPointColor = (pointIndex: number, alpha: number = 1.0): string => {
  const hue = (pointIndex * 90) % 360 // 0°, 90°, 180°, 270°
  return `hsla(${hue}, 70%, 55%, ${alpha})`
}

/**
 * System-wide color constants - Matching LiveStreamsTab theme
 */
export const SYSTEM_COLORS = {
  // Background colors
  canvasBackground: '#212121', // Dark gray
  cardBackground: '#212121', // Dark gray for cards
  gridLines: '#374151', // Gray-700
  border: '#8e8e8e30', // Light gray with opacity

  // Primary gradient colors
  primaryGradientFrom: '#38bd85',
  primaryGradientTo: '#2da89b',

  // UI element colors
  origin: '#60a5fa', // Blue-400
  centerPoint: '#60a5fa',
  selected: '#ffffff',

  // Brand colors
  primary: '#38bd85', // Green
  secondary: '#e9833a', // Orange
  neutral: '#8e8e8e', // Light gray

  // Text colors
  label: '#ffffff',
  sublabel: '#000000',
  coordinates: '#8e8e8e', // Light gray
  textSecondary: '#8e8e8e',

  // Status colors
  success: '#38bd85', // Green matching primary
  warning: '#e9833a', // Orange matching secondary
  error: '#ef4444', // Red-500
  info: '#3b82f6', // Blue-500

  // Cross-camera tracking
  crossCamera: '#38bd85', // Green matching primary
  singleCamera: '#8e8e8e', // Gray

  // Legend colors
  legend: {
    tracks: '#3b82f6',
    calibration: '#e9833a',
    crossCamera: '#38bd85',
    origin: '#60a5fa'
  }
} as const

/**
 * Get color for cross-camera vs single camera tracks
 */
export const getTrackTypeColor = (isGlobal: boolean): string => {
  return isGlobal ? SYSTEM_COLORS.crossCamera : SYSTEM_COLORS.singleCamera
}

/**
 * Generate colors for trajectory trails with fade effect
 */
export const getTrajectoryColors = (trackIndex: number, pointCount: number, globalId?: number) => {
  const baseValue = globalId !== undefined && globalId !== null ? globalId : trackIndex
  const hue = (baseValue * 137.5) % 360

  return Array.from({ length: pointCount }, (_, i) => {
    const alpha = (i + 1) / pointCount // Fade from old to new
    return `hsla(${hue}, 70%, 60%, ${alpha * 0.6})`
  })
}

/**
 * Color accessibility helper
 */
export const getContrastColor = (backgroundColor: string): string => {
  // Simple contrast determination - in a real app you'd use a proper algorithm
  return backgroundColor.includes('light') || backgroundColor.includes('70%') ? '#000000' : '#ffffff'
}

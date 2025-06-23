import React from 'react'

interface StreamError {
  type: string
  message: string
  retryable: boolean
  timestamp: number
}

interface StreamErrorOverlayProps {
  error: StreamError | null
  isVisible: boolean
  onRetry: () => void
}

export function StreamErrorOverlay({ error, isVisible, onRetry }: StreamErrorOverlayProps) {
  if (!isVisible || !error) {
    return null
  }

  return (
    <div className="absolute inset-0 bg-red-900 bg-opacity-75 flex items-center justify-center z-20">
      <div className="text-center p-4">
        <div className="text-red-200 text-lg mb-2">⚠️ Combined Stream Error</div>
        <div className="text-red-100 text-sm mb-3">{error.message}</div>
        {error.retryable && (
          <button
            onClick={onRetry}
            className="px-3 py-1 bg-red-600 text-white rounded text-sm hover:bg-red-700 transition-colors"
          >
            Retry Connection
          </button>
        )}
      </div>
    </div>
  )
}

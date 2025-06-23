import React from 'react'
import { LoadingSpinner } from '../LoadingSpinner'

type CombinedStreamState = 'disconnected' | 'connecting' | 'negotiating' | 'waiting_for_media' | 'streaming' | 'error'

interface StreamLoadingOverlayProps {
  state: CombinedStreamState
}

export function StreamLoadingOverlay({ state }: StreamLoadingOverlayProps) {
  const isLoading = state === 'connecting' || state === 'negotiating' || state === 'waiting_for_media'

  if (!isLoading) {
    return null
  }

  const getMessage = (): string => {
    switch (state) {
      case 'connecting':
        return 'Connecting to server...'
      case 'negotiating':
        return 'Establishing WebRTC connection...'
      case 'waiting_for_media':
        return 'Waiting for combined video frames...'
      default:
        return 'Loading...'
    }
  }

  return (
    <LoadingSpinner
      size="lg"
      message={getMessage()}
      color="white"
      fullOverlay={true}
    />
  )
}

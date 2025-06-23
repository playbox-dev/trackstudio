import { useState, useEffect } from 'react'
import { useAppDispatch, useAppSelector } from '../store/hooks'
import { setStreamDelay, selectStreamDelay } from '../store/slices/streamSlice'
import { SYSTEM_COLORS } from '../utils/colors'
import { ClockIcon } from '@heroicons/react/24/outline'

interface StreamDelayControlsProps {
  streamId: number
  streamName: string
  disabled?: boolean
}

export function StreamDelayControls({
  streamId,
  streamName,
  disabled = false
}: StreamDelayControlsProps) {
  const dispatch = useAppDispatch()
  const reduxDelay = useAppSelector(selectStreamDelay(streamId.toString()))
  const [localDelay, setLocalDelay] = useState<number>(reduxDelay)
  const [isUpdating, setIsUpdating] = useState(false)

  // Sync local state with Redux state
  useEffect(() => {
    setLocalDelay(reduxDelay)
  }, [reduxDelay])

  const handleDelayChange = (value: number) => {
    setLocalDelay(value)
  }

  const handleDelayRelease = async (value: number) => {
    setIsUpdating(true)
    try {
      const response = await fetch(`/api/cameras/stream-delays/${streamId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ delay_ms: value })
      })

      if (response.ok) {
        // Update Redux state
        dispatch(setStreamDelay({ streamId: streamId.toString(), delay: value }))
      } else {
        // Revert to Redux state on error
        setLocalDelay(reduxDelay)
      }
    } catch (error) {
      console.error('Failed to update delay:', error)
      // Revert to Redux state on error
      setLocalDelay(reduxDelay)
    } finally {
      setIsUpdating(false)
    }
  }

  const sliderStyle = {
    width: '100%',
    height: '8px',
    borderRadius: '4px',
    background: SYSTEM_COLORS.gridLines,
    outline: 'none',
    opacity: disabled || isUpdating ? 0.5 : 1,
    transition: 'opacity 0.2s',
    cursor: disabled || isUpdating ? 'not-allowed' : 'pointer',
    // WebKit browsers (Chrome, Safari, Edge)
    WebkitAppearance: 'none' as any,
    // Firefox
    MozAppearance: 'none' as any,
  }

  const sliderThumbStyle = `
    input[type="range"]::-webkit-slider-thumb {
      appearance: none;
      width: 18px;
      height: 18px;
      border-radius: 50%;
      background: ${SYSTEM_COLORS.info};
      cursor: pointer;
      border: 2px solid ${SYSTEM_COLORS.canvasBackground};
      box-shadow: 0 2px 4px rgba(0,0,0,0.3);
      transition: all 0.2s ease;
    }

    input[type="range"]::-webkit-slider-thumb:hover {
      transform: scale(1.1);
      background: ${SYSTEM_COLORS.info}DD;
    }

    input[type="range"]::-moz-range-thumb {
      appearance: none;
      width: 18px;
      height: 18px;
      border-radius: 50%;
      background: ${SYSTEM_COLORS.info};
      cursor: pointer;
      border: 2px solid ${SYSTEM_COLORS.canvasBackground};
      box-shadow: 0 2px 4px rgba(0,0,0,0.3);
      transition: all 0.2s ease;
    }

    input[type="range"]::-moz-range-thumb:hover {
      transform: scale(1.1);
      background: ${SYSTEM_COLORS.info}DD;
    }

    input[type="range"]::-moz-range-track {
      background: ${SYSTEM_COLORS.gridLines};
      height: 8px;
      border-radius: 4px;
      border: none;
    }
  `

  return (
    <div className="p-4 rounded-lg" style={{ backgroundColor: SYSTEM_COLORS.canvasBackground }}>
      <style dangerouslySetInnerHTML={{ __html: sliderThumbStyle }} />

      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center space-x-2">
          <ClockIcon className="w-4 h-4" style={{ color: SYSTEM_COLORS.info }} />
          <h3 className="text-sm font-medium" style={{ color: SYSTEM_COLORS.coordinates }}>
            {streamName} Delay
          </h3>
        </div>
        <span className="text-sm font-mono" style={{ color: SYSTEM_COLORS.label }}>
          {localDelay} ms
        </span>
      </div>

      <div className="flex items-center space-x-4">
        <input
          type="range"
          min="0"
          max="5000"
          step="100"
          value={localDelay}
          onChange={(e) => handleDelayChange(Number(e.target.value))}
          onMouseUp={(e) => handleDelayRelease(Number(e.currentTarget.value))}
          onTouchEnd={(e) => handleDelayRelease(Number(e.currentTarget.value))}
          disabled={disabled || isUpdating}
          className="flex-1"
          style={sliderStyle}
        />

        {/* Quick preset buttons */}
        <div className="flex space-x-1">
          {[
            { label: '0', value: 0 },
            { label: '0.5s', value: 500 },
            { label: '1s', value: 1000 },
            { label: '2s', value: 2000 }
          ].map(({ label, value }) => (
            <button
              key={value}
              onClick={() => {
                setLocalDelay(value)
                handleDelayRelease(value)
              }}
              disabled={disabled || isUpdating}
              className={`px-2 py-1 text-xs rounded transition-colors ${
                disabled || isUpdating ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'
              }`}
              style={{
                backgroundColor: localDelay === value ? SYSTEM_COLORS.info : SYSTEM_COLORS.gridLines,
                color: localDelay === value ? SYSTEM_COLORS.canvasBackground : SYSTEM_COLORS.coordinates
              }}
              onMouseEnter={(e) => {
                if (!disabled && !isUpdating && localDelay !== value) {
                  e.currentTarget.style.backgroundColor = SYSTEM_COLORS.canvasBackground
                }
              }}
              onMouseLeave={(e) => {
                if (!disabled && !isUpdating && localDelay !== value) {
                  e.currentTarget.style.backgroundColor = SYSTEM_COLORS.gridLines
                }
              }}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      {isUpdating && (
        <div className="mt-2 text-xs" style={{ color: SYSTEM_COLORS.warning }}>
          Applying delay...
        </div>
      )}

      <div className="mt-2 text-xs" style={{ color: SYSTEM_COLORS.coordinates }}>
        Adjust to synchronize streams (0-5000ms)
      </div>
    </div>
  )
}

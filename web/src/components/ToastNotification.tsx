import { useEffect, useState } from 'react'

interface ToastNotificationProps {
  message: string
  type: 'success' | 'error' | 'warning' | 'info'
  duration?: number
  onClose: () => void
}

export function ToastNotification({
  message,
  type,
  duration = 5000,
  onClose
}: ToastNotificationProps) {
  const [isVisible, setIsVisible] = useState(false)
  const [isExiting, setIsExiting] = useState(false)

  useEffect(() => {
    // Animate in
    setIsVisible(true)

    // Auto-close after duration
    const timer = setTimeout(() => {
      handleClose()
    }, duration)

    return () => clearTimeout(timer)
  }, [duration])

  const handleClose = () => {
    setIsExiting(true)
    setTimeout(() => {
      onClose()
    }, 300) // Match the animation duration
  }

  const getTypeStyles = () => {
    switch (type) {
      case 'success':
        return 'bg-gradient-to-r from-[#38bd85] to-[#2da89b] border-[#2da89b] text-white'
      case 'error':
        return 'bg-red-600 border-red-500 text-white'
      case 'warning':
        return 'bg-[#e9833a] border-[#e9833a] text-white'
      case 'info':
        return 'bg-[#212121] border-[#8e8e8e] text-white'
      default:
        return 'bg-[#8e8e8e] border-[#8e8e8e] text-white'
    }
  }

  const getIcon = () => {
    switch (type) {
      case 'success': return '✅'
      case 'error': return '❌'
      case 'warning': return '⚠️'
      case 'info': return 'ℹ️'
      default: return '📢'
    }
  }

  return (
    <div
      className={`
        w-full
        border-l-4 rounded-lg shadow-lg p-4
        transition-all duration-300 ease-in-out transform
        ${getTypeStyles()}
        ${isVisible && !isExiting
          ? 'scale-100 opacity-100'
          : 'scale-95 opacity-0'
        }
      `}
    >
      <div className="flex items-start">
        <div className="text-xl mr-3 flex-shrink-0">
          {getIcon()}
        </div>
        <div className="flex-1 min-w-0">
          <div className="text-sm font-medium break-words">
            {message}
          </div>
        </div>
        <button
          onClick={handleClose}
          className="ml-4 text-lg hover:opacity-70 transition-opacity flex-shrink-0"
        >
          ×
        </button>
      </div>
    </div>
  )
}

interface ToastContainerProps {
  toasts: Array<{
    id: string
    message: string
    type: 'success' | 'error' | 'warning' | 'info'
  }>
  onRemoveToast: (id: string) => void
}

export function ToastContainer({ toasts, onRemoveToast }: ToastContainerProps) {
  return (
    <div className="fixed top-4 left-0 right-0 z-50 pointer-events-none">
      <div className="w-4/5 max-w-[2000px] mx-auto px-6">
        <div className="flex justify-end">
          <div className="space-y-2 w-80">
            {toasts.map((toast) => (
              <div key={toast.id} className="pointer-events-auto">
                <ToastNotification
                  message={toast.message}
                  type={toast.type}
                  onClose={() => onRemoveToast(toast.id)}
                />
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}

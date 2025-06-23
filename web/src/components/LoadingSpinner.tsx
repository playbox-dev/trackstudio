

interface LoadingSpinnerProps {
  size?: 'sm' | 'md' | 'lg'
  message?: string
  color?: 'white' | 'blue' | 'yellow' | 'red'
  fullOverlay?: boolean
}

export function LoadingSpinner({
  size = 'md',
  message,
  color = 'white',
  fullOverlay = false
}: LoadingSpinnerProps) {
  const sizeClasses = {
    sm: 'h-4 w-4',
    md: 'h-8 w-8',
    lg: 'h-12 w-12'
  }

  const colorClasses = {
    white: 'border-white',
    blue: 'border-blue-500',
    yellow: 'border-yellow-500',
    red: 'border-red-500'
  }

  const textColorClasses = {
    white: 'text-white',
    blue: 'text-blue-500',
    yellow: 'text-yellow-500',
    red: 'text-red-500'
  }

  const spinner = (
    <div className="flex flex-col items-center justify-center">
      <div
        className={`animate-spin rounded-full border-b-2 ${sizeClasses[size]} ${colorClasses[color]} mb-2`}
      />
      {message && (
        <div className={`text-sm ${textColorClasses[color]} text-center`}>
          {message}
        </div>
      )}
    </div>
  )

  if (fullOverlay) {
    return (
      <div className="absolute inset-0 bg-black bg-opacity-50 flex items-center justify-center z-10">
        {spinner}
      </div>
    )
  }

  return spinner
}

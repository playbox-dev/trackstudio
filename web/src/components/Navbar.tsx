import type { ConnectionStatus } from '../types'

interface NavbarProps {
  connectionStatus: ConnectionStatus
}

export function Navbar({ connectionStatus }: NavbarProps) {
  const getStatusText = (status: ConnectionStatus) => {
    return status.charAt(0).toUpperCase() + status.slice(1)
  }

  return (
    <nav className="bg-[#1a1a1a] border-b border-[#8e8e8e]/30">
      <div className="w-4/5 max-w-[2000px] mx-auto px-6">
        <div className="flex items-center justify-between h-16">
          <div className="flex items-center space-x-3">
            {/* Logo */}
            <img
              src="/favicon.svg"
              alt="TrackStudio Logo"
              width="32"
              height="32"
              className="w-8 h-8"
            />

            <span className="text-2xl font-medium text-white font-baumans">
              Track Studio
            </span>
          </div>

          <div className="flex items-center">
            <span className={`status-indicator status-${connectionStatus}`}></span>
            <span className="text-sm ml-2 text-white">
              {getStatusText(connectionStatus)}
            </span>
          </div>
        </div>
      </div>
    </nav>
  )
}

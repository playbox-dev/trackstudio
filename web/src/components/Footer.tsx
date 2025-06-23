
export function Footer() {
  const currentYear = new Date().getFullYear()

  return (
    <footer className="bg-[#1a1a1a] border-t border-[#8e8e8e]/20 mt-auto">
      <div className="w-4/5 max-w-[2000px] mx-auto px-6 py-8">
        <div className="flex flex-col md:flex-row justify-between items-center space-y-4 md:space-y-0">

          {/* Left side - Attribution */}
          <div className="flex flex-col md:flex-row items-center space-y-2 md:space-y-0 md:space-x-6">
            <div className="flex items-center space-x-2">
              <span className="text-sm text-[#8e8e8e]">Made by</span>
              <a
                href="https://www.play-box.ai"
                className="text-sm font-semibold text-transparent bg-gradient-to-r from-[#38bd85] to-[#2da89b] bg-clip-text hover:from-[#2da89b] hover:to-[#38bd85] transition-colors duration-200"
                target="_blank"
                rel="strict-origin-when-cross-origin"
              >
                playbox
              </a>
            </div>

            <div className="hidden md:block w-px h-4 bg-[#8e8e8e]/30"></div>

            <div className="flex items-center space-x-4 text-xs text-[#8e8e8e]">
              <span>© {currentYear} Playbox Team</span>
              <span>•</span>
              <span>Apache License</span>
              <span>•</span>
              <span>v0.1.0</span>
            </div>
          </div>

          {/* Right side - Links */}
          <div className="flex items-center space-x-4">
            <a
              href="https://github.com/playbox-dev/trackstudio"
              className="flex items-center space-x-2 text-sm text-[#8e8e8e] hover:text-white transition-colors duration-200"
              target="_blank"
              rel="noopener noreferrer"
            >
              <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
                <path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z"/>
              </svg>
              <span>Source Code</span>
            </a>

            <a
              href="https://github.com/playbox-dev/trackstudio/blob/main/LICENSE"
              className="text-sm text-[#8e8e8e] hover:text-white transition-colors duration-200"
              target="_blank"
              rel="noopener noreferrer"
            >
              License
            </a>

            <a
              href="https://github.com/playbox-dev/trackstudio/issues"
              className="text-sm text-[#8e8e8e] hover:text-white transition-colors duration-200"
              target="_blank"
              rel="noopener noreferrer"
            >
              Report Issue
            </a>
          </div>
        </div>

        {/* Bottom text */}
        {/* <div className="mt-6 pt-4 border-t border-[#8e8e8e]/10">
          <p className="text-xs text-[#8e8e8e] text-center">
            TrackStudio is an open-source multi-camera vision tracking system.
            <span className="mx-1">•</span>
            <a
              href="https://trackstudio.readthedocs.io/"
              className="hover:text-white transition-colors duration-200"
              target="_blank"
              rel="noopener noreferrer"
            >
              Documentation
            </a>
          </p>
        </div> */}
      </div>
    </footer>
  )
}

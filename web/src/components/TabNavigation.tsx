import {
  VideoCameraIcon,
  ViewColumnsIcon,
  MapIcon,
  WrenchScrewdriverIcon,
} from '@heroicons/react/24/outline'

interface TabNavigationProps {
  activeTab: 'streams' | 'bev' | 'calibration' | 'combined'
  onTabChange: (tab: 'streams' | 'bev' | 'calibration' | 'combined') => void
}

export function TabNavigation({ activeTab, onTabChange }: TabNavigationProps) {
  const tabs = [
    { id: 'streams', label: 'Live Streams', icon: VideoCameraIcon },
    { id: 'combined', label: 'Combined View', icon: ViewColumnsIcon },
    { id: 'bev', label: "Bird's Eye View", icon: MapIcon },
    { id: 'calibration', label: 'Calibration', icon: WrenchScrewdriverIcon },
  ] as const

  return (
    <div className="border-b border-[#8e8e8e]/30">
      <nav className="flex space-x-8">
        {tabs.map((tab) => {
          const IconComponent = tab.icon
          return (
            <button
              key={tab.id}
              onClick={() => onTabChange(tab.id)}
              className={`py-4 px-1 border-b-2 font-medium text-sm transition-colors flex items-center ${
                activeTab === tab.id
                  ? 'border-[#2da89b] text-transparent bg-gradient-to-r from-[#38bd85] to-[#2da89b] bg-clip-text'
                  : 'border-transparent text-[#8e8e8e] hover:text-white hover:border-[#8e8e8e]/50'
              }`}
            >
              <IconComponent className={`w-5 h-5 mr-2 ${
                activeTab === tab.id ? 'text-[#2da89b]' : ''
              }`} />
              {tab.label}
            </button>
          )
        })}
      </nav>
    </div>
  )
}

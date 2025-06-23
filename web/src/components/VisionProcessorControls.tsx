import React, { useEffect, useState, useCallback } from 'react';
import { getVisionProcessorSchema, getVisionProcessorConfig, updateVisionProcessorConfig, restartVisionSystem } from '../services/vision';
import { ChevronDownIcon, ChevronUpIcon, ArrowPathIcon } from '@heroicons/react/24/solid';

// Simple debounce function to replace lodash
const debounce = (func: (...args: any[]) => void, delay: number) => {
  let timeoutId: ReturnType<typeof setTimeout>;
  return (...args: any[]) => {
    clearTimeout(timeoutId);
    timeoutId = setTimeout(() => func(...args), delay);
  };
};

// Define types for the schema and config
interface ParamSchema {
  title: string;
  description: string;
  type: string;
  default?: any;
  ui_control?: 'slider';
  min?: number;
  max?: number;
  step?: number;
  properties?: Record<string, ParamSchema>;
}

interface Schema {
  properties: Record<string, ParamSchema>;
  [key: string]: any;
}

type Config = Record<string, any>;

const VisionProcessorControls: React.FC = () => {
  const [schema, setSchema] = useState<Schema | null>(null);
  const [config, setConfig] = useState<Config | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [openSections, setOpenSections] = useState<Record<string, boolean>>({});
  const [restarting, setRestarting] = useState<boolean>(false);
  const [showRestartConfirm, setShowRestartConfirm] = useState<boolean>(false);

  const debouncedUpdateConfig = useCallback(
    debounce((updatePayload: object) => {
      updateVisionProcessorConfig(updatePayload);
    }, 500),
    []
  );

  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true);
        const schemaData = await getVisionProcessorSchema();
        const configData = await getVisionProcessorConfig();
        console.log('Fetched schema:', schemaData);
        console.log('Fetched config:', configData);
        setSchema(schemaData);
        setConfig(configData);
        const initialSections: Record<string, boolean> = {};
        if (schemaData && schemaData.properties) {
          Object.keys(schemaData.properties).forEach(key => {
            initialSections[key] = true; // Open top-level sections by default
            if(schemaData.properties[key].properties) {
              Object.keys(schemaData.properties[key].properties!).forEach(subKey => {
                 initialSections[`${key}.${subKey}`] = true; // Open sub-sections by default
              });
            }
          });
        }
        setOpenSections(initialSections);
        setError(null);
      } catch (err) {
        setError('Failed to load vision processor configuration.');
        console.error('VisionProcessorControls error:', err);
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, []);

  const handleParamChange = (path: string[], value: any) => {
    setConfig(currentConfig => {
        const newConfig = JSON.parse(JSON.stringify(currentConfig));
        let config_level = newConfig;
        for(let i=0; i < path.length - 1; i++) {
            config_level = config_level[path[i]];
        }
        config_level[path[path.length-1]] = value;

        // Construct payload for backend
        const updatePayload = {};
        let payload_level: any = updatePayload;
        for(let i=0; i < path.length - 1; i++) {
            payload_level[path[i]] = {};
            payload_level = payload_level[path[i]];
        }
        payload_level[path[path.length-1]] = value;

        debouncedUpdateConfig(updatePayload);
        return newConfig;
    });
  };

  const toggleSection = (sectionPath: string) => {
    setOpenSections(prev => ({ ...prev, [sectionPath]: !prev[sectionPath] }));
  };

  const handleRestartSystem = async (preserveCalibration: boolean = true) => {
    try {
      setRestarting(true);
      setError(null);
      console.log('🔄 Restarting vision system...');

      const result = await restartVisionSystem(preserveCalibration);
      console.log('✅ Vision system restarted:', result);

      // Optionally show success message or toast
      setShowRestartConfirm(false);

    } catch (err) {
      console.error('❌ Vision system restart failed:', err);
      setError('Failed to restart vision system. Check logs for details.');
    } finally {
      setRestarting(false);
    }
  };

  const renderControls = (schemaProps: Record<string, ParamSchema>, path: string[]) => {
    return Object.entries(schemaProps).map(([key, paramSchema]) => {
      const currentPath = [...path, key];
      const currentPathStr = currentPath.join('.');

      if (paramSchema.ui_control === 'slider') {
        let value: any = config;
        for(const p of currentPath) {
          value = value?.[p];
        }
        value = value ?? paramSchema.default;

        const step = paramSchema.step || 1;
        const numericValue = typeof value === 'number' ? value : parseFloat(value) || 0;
        const fixedValue = Math.round(numericValue / step) * step;

        return (
          <div key={currentPathStr} className="grid grid-cols-3 gap-4 items-center mb-2">
            <label className="text-sm text-[#8e8e8e] col-span-1" title={paramSchema.description}>
              {paramSchema.title || key}
            </label>
            <input
              type="range"
              min={paramSchema.min}
              max={paramSchema.max}
              step={paramSchema.step}
              value={numericValue}
              onChange={(e) => handleParamChange(currentPath, parseFloat(e.target.value))}
              className="col-span-1 h-2 bg-[#8e8e8e]/20 rounded-lg appearance-none cursor-pointer slider-gradient"
            />
            <span className="text-sm font-mono text-transparent bg-gradient-to-r from-[#38bd85] to-[#2da89b] bg-clip-text col-span-1 text-right">
              {fixedValue.toFixed(step < 1 ? 2 : 0)}
            </span>
          </div>
        );
      }
      return null;
    });
  };

  const renderSection = (sectionKey: string, sectionSchema: ParamSchema) => {
    const isTopLevelSectionOpen = openSections[sectionKey];

    // Check if this section contains subsections or direct controls
    const hasSubsections = sectionSchema.properties ?
      Object.values(sectionSchema.properties).some(p => p && p.properties) : false;

    return (
      <div key={sectionKey} className="mb-2 border border-[#8e8e8e]/30 rounded-lg">
        <button
          onClick={() => toggleSection(sectionKey)}
          className="w-full bg-[#1a1a1a] p-3 text-left font-bold flex justify-between items-center rounded-t-lg hover:bg-[#2a2a2a]"
        >
          <span>{sectionSchema.title || sectionKey}</span>
          {isTopLevelSectionOpen ? <ChevronUpIcon className="w-5 h-5"/> : <ChevronDownIcon className="w-5 h-5"/>}
        </button>
        {isTopLevelSectionOpen && (
          <div className="p-4">
            {hasSubsections ? (
              // Render subsections
              sectionSchema.properties ? Object.entries(sectionSchema.properties).map(([subKey, subSchema]) => (
                subSchema ? (
                                  <div key={subKey} className="mb-4">
                  <h4 className="text-md font-semibold mb-2 text-white border-b border-[#8e8e8e]/30 pb-1">{subSchema.title || subKey}</h4>
                  <div className="pt-2">
                    {subSchema.properties ? renderControls(subSchema.properties, [sectionKey, subKey]) : null}
                  </div>
                </div>
                ) : null
              )) : null
            ) : (
              // Render direct controls
              sectionSchema.properties ? renderControls(sectionSchema.properties, [sectionKey]) : null
            )}
          </div>
        )}
      </div>
    );
  };

  if (loading) return <div className="text-center p-4">Loading processor controls...</div>;
  if (error) return <div className="text-center p-4 text-red-500">{error}</div>;
  if (!schema || !config) return <div className="text-center p-4">No configuration available for this processor.</div>;

  return (
    <div className="bg-[#212121] border border-[#8e8e8e]/30 rounded-lg p-4 text-white">
      {/* Restart System Section */}
      <div className="mb-4 p-3 bg-[#1a1a1a] border border-[#8e8e8e]/20 rounded-lg">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-sm font-semibold text-white">System Control</h3>
            <p className="text-xs text-[#8e8e8e]">Restart tracker and merger with current config</p>
          </div>
          <button
            onClick={() => setShowRestartConfirm(true)}
            disabled={restarting}
            className={`flex items-center gap-2 px-3 py-2 rounded-md transition-all ${
              restarting
                ? 'bg-[#8e8e8e]/20 text-[#8e8e8e] cursor-not-allowed'
                : 'bg-gradient-to-r from-[#38bd85] to-[#2da89b] hover:from-[#2da89b] hover:to-[#38bd85] text-white hover:shadow-lg'
            }`}
          >
            <ArrowPathIcon className={`w-4 h-4 ${restarting ? 'animate-spin' : ''}`} />
            <span className="text-sm font-medium">
              {restarting ? 'Restarting...' : 'Restart System'}
            </span>
          </button>
        </div>

        {/* Confirmation Dialog */}
        {showRestartConfirm && (
          <div className="mt-3 p-3 bg-[#2a2a2a] border border-[#8e8e8e]/30 rounded-md">
            <p className="text-sm text-[#8e8e8e] mb-3">
              This will restart the tracker and merger, resetting all tracking states. Calibration data will be preserved.
            </p>
            <div className="flex gap-2">
              <button
                onClick={() => handleRestartSystem(true)}
                disabled={restarting}
                className="flex-1 px-3 py-2 bg-gradient-to-r from-[#38bd85] to-[#2da89b] text-white text-sm rounded-md hover:shadow-lg transition-all"
              >
                Restart & Keep Calibration
              </button>
              <button
                onClick={() => handleRestartSystem(false)}
                disabled={restarting}
                className="flex-1 px-3 py-2 bg-red-600 hover:bg-red-700 text-white text-sm rounded-md transition-all"
              >
                Restart & Clear All
              </button>
              <button
                onClick={() => setShowRestartConfirm(false)}
                className="px-3 py-2 border border-[#8e8e8e]/30 text-[#8e8e8e] text-sm rounded-md hover:bg-[#3a3a3a] transition-all"
              >
                Cancel
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Configuration Sections */}
      {schema.properties && typeof schema.properties === 'object' ?
        Object.entries(schema.properties).map(([sectionKey, sectionSchema]) =>
          sectionSchema ? renderSection(sectionKey, sectionSchema) : null
        ) :
        <div className="text-center text-[#8e8e8e]">No configuration sections available</div>
      }
    </div>
  );
};

export default VisionProcessorControls;

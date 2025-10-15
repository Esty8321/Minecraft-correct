import React from 'react';
import { Palette, X, Monitor, Moon, Sun } from 'lucide-react';
import { ChatTheme } from '../../types';

interface CustomizationPanelProps {
  currentTheme: ChatTheme;
  themes: ChatTheme[];
  onThemeChange: (theme: ChatTheme) => void;
  onClose: () => void;
}

const CustomizationPanel: React.FC<CustomizationPanelProps> = ({
  currentTheme,
  themes,
  onThemeChange,
  onClose
}) => {
  return (
    <div className="absolute top-16 right-4 bg-slate-800 border border-slate-600 rounded-xl shadow-2xl z-50 w-80">
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-slate-600">
        <div className="flex items-center gap-2">
          <Palette className="w-5 h-5 text-cyan-400" />
          <h3 className="text-lg font-semibold text-white">Customize Chat</h3>
        </div>
        <button
          onClick={onClose}
          className="p-2 text-slate-400 hover:text-white hover:bg-slate-700 rounded-lg transition-colors"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* Theme Selection */}
      <div className="p-4">
        <h4 className="text-sm font-medium text-slate-300 mb-3 flex items-center gap-2">
          <Monitor className="w-4 h-4" />
          Choose Theme
        </h4>
        <div className="space-y-2">
          {themes.map((theme, index) => (
            <button
              key={index}
              onClick={() => onThemeChange(theme)}
              className={`
                w-full p-3 rounded-lg text-left transition-all duration-200 hover:scale-105
                ${currentTheme.name === theme.name
                  ? 'ring-2 ring-cyan-500 bg-slate-700'
                  : 'hover:bg-slate-700'
                }
              `}
            >
              <div className="flex items-center justify-between">
                <div>
                  <div className="text-white font-medium">{theme.name}</div>
                  <div className="flex gap-2 mt-2">
                    <div
                      className="w-4 h-4 rounded-full border border-slate-600"
                      style={{ backgroundColor: theme.primaryColor }}
                    />
                    <div
                      className="w-4 h-4 rounded-full border border-slate-600"
                      style={{ backgroundColor: theme.secondaryColor }}
                    />
                    <div
                      className="w-4 h-4 rounded-full border border-slate-600"
                      style={{ backgroundColor: theme.accentColor }}
                    />
                  </div>
                </div>
                {currentTheme.name === theme.name && (
                  <div className="w-2 h-2 bg-cyan-400 rounded-full"></div>
                )}
              </div>
            </button>
          ))}
        </div>

        {/* Additional Options */}
        <div className="mt-6 pt-4 border-t border-slate-600">
          <h4 className="text-sm font-medium text-slate-300 mb-3">Additional Options</h4>
          
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-sm text-slate-300">Dark Mode</span>
              <div className="flex items-center gap-2">
                <Sun className="w-4 h-4 text-slate-400" />
                <div className="w-12 h-6 bg-slate-600 rounded-full relative cursor-pointer">
                  <div className="w-5 h-5 bg-cyan-400 rounded-full absolute top-0.5 left-6 transition-all duration-200"></div>
                </div>
                <Moon className="w-4 h-4 text-cyan-400" />
              </div>
            </div>
            
            <div className="flex items-center justify-between">
              <span className="text-sm text-slate-300">Sound Effects</span>
              <div className="w-12 h-6 bg-cyan-600 rounded-full relative cursor-pointer">
                <div className="w-5 h-5 bg-white rounded-full absolute top-0.5 right-0.5 transition-all duration-200"></div>
              </div>
            </div>
            
            <div className="flex items-center justify-between">
              <span className="text-sm text-slate-300">Auto-scroll</span>
              <div className="w-12 h-6 bg-cyan-600 rounded-full relative cursor-pointer">
                <div className="w-5 h-5 bg-white rounded-full absolute top-0.5 right-0.5 transition-all duration-200"></div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default CustomizationPanel;
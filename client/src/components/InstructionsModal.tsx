import React from "react";
import { X, Keyboard, MessageSquare, Palette, ArrowUp, ArrowDown, ArrowLeft, ArrowRight } from "lucide-react";

interface InstructionsModalProps {
  onClose: () => void;
}

export const InstructionsModal: React.FC<InstructionsModalProps> = ({ onClose }) => {
  return (
    <div className="fixed inset-0 z-[10002] flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-fadeIn">
      <div className="relative bg-gradient-to-br from-slate-800 to-slate-900 rounded-3xl shadow-2xl border border-slate-700/50 max-w-2xl w-full max-h-[90vh] overflow-hidden animate-slideUp">
        <div className="absolute inset-0 bg-gradient-to-br from-blue-500/5 to-purple-500/5 pointer-events-none" />

        <div className="relative">
          <div className="flex items-center justify-between p-6 border-b border-slate-700/50">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-gradient-to-br from-blue-500 to-purple-500 rounded-xl">
                <Keyboard size={24} className="text-white" />
              </div>
              <h2 className="text-2xl font-bold bg-gradient-to-r from-blue-400 to-purple-400 bg-clip-text text-transparent">
                How to Play
              </h2>
            </div>
            <button
              onClick={onClose}
              className="p-2 hover:bg-slate-700/50 rounded-full transition-colors"
              aria-label="Close"
            >
              <X size={24} className="text-slate-400" />
            </button>
          </div>

          <div className="p-6 overflow-y-auto max-h-[calc(90vh-120px)]">
            <div className="space-y-6">
              <section>
                <h3 className="text-xl font-semibold text-white mb-4 flex items-center gap-2">
                  <ArrowUp size={20} className="text-blue-400" />
                  Movement Controls
                </h3>
                <div className="grid grid-cols-2 gap-3">
                  <div className="bg-slate-800/50 rounded-xl p-4 border border-slate-700/30">
                    <div className="flex items-center gap-3 mb-2">
                      <kbd className="px-3 py-1.5 bg-slate-700 rounded-lg text-sm font-mono text-slate-200 shadow-md">
                        W
                      </kbd>
                      <span className="text-slate-300">or</span>
                      <kbd className="px-3 py-1.5 bg-slate-700 rounded-lg text-sm font-mono text-slate-200 shadow-md">
                        ↑
                      </kbd>
                    </div>
                    <p className="text-sm text-slate-400">Move up</p>
                  </div>

                  <div className="bg-slate-800/50 rounded-xl p-4 border border-slate-700/30">
                    <div className="flex items-center gap-3 mb-2">
                      <kbd className="px-3 py-1.5 bg-slate-700 rounded-lg text-sm font-mono text-slate-200 shadow-md">
                        S
                      </kbd>
                      <span className="text-slate-300">or</span>
                      <kbd className="px-3 py-1.5 bg-slate-700 rounded-lg text-sm font-mono text-slate-200 shadow-md">
                        ↓
                      </kbd>
                    </div>
                    <p className="text-sm text-slate-400">Move down</p>
                  </div>

                  <div className="bg-slate-800/50 rounded-xl p-4 border border-slate-700/30">
                    <div className="flex items-center gap-3 mb-2">
                      <kbd className="px-3 py-1.5 bg-slate-700 rounded-lg text-sm font-mono text-slate-200 shadow-md">
                        A
                      </kbd>
                      <span className="text-slate-300">or</span>
                      <kbd className="px-3 py-1.5 bg-slate-700 rounded-lg text-sm font-mono text-slate-200 shadow-md">
                        ←
                      </kbd>
                    </div>
                    <p className="text-sm text-slate-400">Move left</p>
                  </div>

                  <div className="bg-slate-800/50 rounded-xl p-4 border border-slate-700/30">
                    <div className="flex items-center gap-3 mb-2">
                      <kbd className="px-3 py-1.5 bg-slate-700 rounded-lg text-sm font-mono text-slate-200 shadow-md">
                        D
                      </kbd>
                      <span className="text-slate-300">or</span>
                      <kbd className="px-3 py-1.5 bg-slate-700 rounded-lg text-sm font-mono text-slate-200 shadow-md">
                        →
                      </kbd>
                    </div>
                    <p className="text-sm text-slate-400">Move right</p>
                  </div>
                </div>
              </section>

              <section>
                <h3 className="text-xl font-semibold text-white mb-4 flex items-center gap-2">
                  <MessageSquare size={20} className="text-purple-400" />
                  Message Controls
                </h3>
                <div className="bg-gradient-to-br from-purple-900/30 to-purple-800/20 rounded-xl p-5 border border-purple-500/30">
                  <div className="flex items-start gap-4">
                    <kbd className="px-4 py-2 bg-purple-700/50 rounded-lg text-lg font-mono text-purple-200 shadow-lg">
                      M
                    </kbd>
                    <div className="flex-1">
                      <h4 className="text-white font-semibold mb-1">Leave a Message</h4>
                      <p className="text-slate-300 text-sm leading-relaxed">
                        Press the <span className="font-semibold text-purple-300">M</span> key to leave a message on your current square.
                        Other players can discover your messages as they explore the world.
                      </p>
                    </div>
                  </div>
                </div>
              </section>

              <section>
                <h3 className="text-xl font-semibold text-white mb-4 flex items-center gap-2">
                  <Palette size={20} className="text-pink-400" />
                  Color Controls
                </h3>
                <div className="bg-gradient-to-br from-pink-900/30 to-pink-800/20 rounded-xl p-5 border border-pink-500/30">
                  <div className="flex items-start gap-4">
                    <kbd className="px-4 py-2 bg-pink-700/50 rounded-lg text-lg font-mono text-pink-200 shadow-lg">
                      C
                    </kbd>
                    <div className="flex-1">
                      <h4 className="text-white font-semibold mb-1">Change Color</h4>
                      <p className="text-slate-300 text-sm leading-relaxed">
                        Press the <span className="font-semibold text-pink-300">C</span> key to cycle through different colors.
                        Express yourself by painting the world with your unique color.
                      </p>
                    </div>
                  </div>
                </div>
              </section>

              <section>
                <h3 className="text-xl font-semibold text-white mb-4 flex items-center gap-2">
                  <MessageSquare size={20} className="text-cyan-400" />
                  Chat Features
                </h3>
                <div className="bg-gradient-to-br from-cyan-900/30 to-cyan-800/20 rounded-xl p-5 border border-cyan-500/30">
                  <div className="space-y-3">
                    <div className="flex items-start gap-3">
                      <div className="w-2 h-2 rounded-full bg-cyan-400 mt-2" />
                      <p className="text-slate-300 text-sm leading-relaxed flex-1">
                        Click the <span className="font-semibold text-cyan-300">chat button</span> in the top-right corner
                        to open the chat panel and talk with other players in real-time.
                      </p>
                    </div>
                    <div className="flex items-start gap-3">
                      <div className="w-2 h-2 rounded-full bg-cyan-400 mt-2" />
                      <p className="text-slate-300 text-sm leading-relaxed flex-1">
                        Connect with other explorers, share discoveries, and coordinate your adventures.
                      </p>
                    </div>
                  </div>
                </div>
              </section>

              <div className="bg-gradient-to-r from-blue-500/10 to-purple-500/10 rounded-xl p-4 border border-blue-500/20">
                <p className="text-slate-300 text-sm text-center leading-relaxed">
                  Explore the voxel world, leave your mark, and discover what others have hidden.
                  <br />
                  <span className="text-blue-300 font-semibold">Happy exploring!</span>
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

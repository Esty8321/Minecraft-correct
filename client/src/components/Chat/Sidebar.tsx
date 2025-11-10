import React, { useState, useEffect } from 'react';
import { Users, Crown } from 'lucide-react';
import { Player } from '../../types';

interface SidebarProps {
  activePlayers: Player[];
  selectedPlayer: Player | null;
  onSelectPlayer: (player: Player) => void;
  currentPlayerId: string;
  unreadCounts?: Record<string, number>;
  onMarkRead?: (playerId: string) => void;
  nearestPlayerId?: string;
}

const Sidebar: React.FC<SidebarProps> = ({
  activePlayers,
  selectedPlayer,
  onSelectPlayer,
  currentPlayerId,
  unreadCounts,
  onMarkRead,
  nearestPlayerId
}) => {
  const [toast, setToast] = useState<string | null>(null);

  useEffect(() => {
    if (toast) {
      const t = setTimeout(() => setToast(null), 2000);
      return () => clearTimeout(t);
    }
  }, [toast]);

  const list = activePlayers.filter(p => p.id !== currentPlayerId);

  return (
    <div className="w-72 h-full border-r border-slate-700 bg-slate-900/50 flex flex-col relative">
      {/* Header */}
      <div className="p-4 border-b border-slate-700 flex items-center gap-2">
        <Users size={18} />
        <div className="font-semibold">Players</div>
      </div>

      {/* Players list */}
      <div className="flex-1 overflow-auto p-3 space-y-2">
        {list.length === 0 ? (
          <div className="text-sm text-slate-400">No players in this chunk.</div>
        ) : (
          list.map((p) => {
            const isSelected = selectedPlayer?.id === p.id;
            const isMe = currentPlayerId === p.id; 
            const isNearest = nearestPlayerId === p.id;
            const unread = unreadCounts?.[p.id] ?? 0;

            return (
              <div
                key={p.id}
                onClick={() => {
                  if (isMe) {
                    setToast("❌ You can't chat with yourself");
                    return;
                  }
                  if (!isNearest) {
                    setToast('💬 You can only chat with the nearest player');
                    return;
                  }
                  onSelectPlayer(p);
                  if (unread > 0 && onMarkRead) onMarkRead(p.id);
                }}
                className={[
                  'flex items-center gap-3 p-2 rounded-lg cursor-pointer border transition-all',
                  isSelected ? 'bg-slate-700 border-slate-500' : 'hover:bg-slate-700/40 border-transparent',
                  isNearest ? 'animate-pulse ring-2 ring-emerald-500/60' : '',
                  !isNearest && !isMe ? 'opacity-60' : '',
                ].join(' ')}
              >
                <div className="relative">
                  <div className="w-9 h-9 rounded-full bg-slate-700 flex items-center justify-center">
                    <Crown size={16} />
                  </div>
                  <span
                    className={`absolute -bottom-1 -right-1 w-3 h-3 rounded-full border border-slate-900
                    ${p.status === 'online' ? 'bg-emerald-500' : p.status === 'in-game' ? 'bg-sky-500' : 'bg-slate-500'}`}
                    title={p.status || 'unknown'}
                  />
                </div>

                <div className="flex-1 min-w-0">
                  <div className="text-sm font-medium truncate">
                    {p.username}
                    {isNearest && (
                      <span className="ml-1 text-xs px-1 py-0.5 rounded bg-sky-600/40 border border-sky-500/60">
                        nearest
                      </span>
                    )}
                  </div>
                  <div className="text-xs text-slate-400 truncate">{(p as any).email || ''}</div>
                </div>

                {unread > 0 && (
                  <div className="text-[10px] bg-rose-600 text-white px-1.5 py-0.5 rounded-full">{unread}</div>
                )}
              </div>
            );
          })
        )}
      </div>

      {/* Footer */}
      <div className="p-4 border-t border-slate-700">
        <div className="text-xs text-slate-400 text-center">🎮 Game Chat • Talk. Play. Enjoy.</div>
      </div>

      {toast && (
        <div className="absolute bottom-6 left-1/2 -translate-x-1/2 bg-emerald-600/90 text-white text-sm px-4 py-2.5 rounded-lg border border-emerald-400 shadow-lg animate-fade-in backdrop-blur-md">
          {toast}
        </div>
      )}
    </div>
  );
};

export default Sidebar;

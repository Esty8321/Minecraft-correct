
import React, { useMemo } from 'react';
import { Users, Crown, Circle } from 'lucide-react';
import { Player } from '../../types';

/**
 * unreadCounts: מפת { playerId: count } מה־WS hook
 * onMarkRead: פונקציה שמסמנת לשרת שקראנו (WS type:"read")
 */
interface SidebarProps {
  activePlayers: Player[];
  selectedPlayer: Player | null;
  onSelectPlayer: (player: Player) => void;
  currentPlayerId: string;
  unreadCounts?: Record<string, number>;
  onMarkRead?: (playerId: string) => void;
}

const Sidebar: React.FC<SidebarProps> = ({
  activePlayers,
  selectedPlayer,
  onSelectPlayer,
  currentPlayerId,
  unreadCounts = {},
  onMarkRead,
}) => {
  const getStatusColor = (status: string) => {
    switch (status) {
      case 'online':
        return 'text-green-400';
      case 'in-game':
        return 'text-yellow-400';
      case 'away':
        return 'text-gray-400';
      default:
        return 'text-green-400';
    }
  };
  // אייקון מצב: 🎮 קטן
  const getStatusIcon = (_status: string) => <div className="text-sm leading-none">🎮</div>;

  // ממו לקיצור רנדרים ברשימות גדולות
  const me = useMemo(
    () => activePlayers.find(p => p.id === currentPlayerId) || null,
    [activePlayers, currentPlayerId]
  );
  const others = useMemo(
    () => activePlayers.filter(p => p.id !== currentPlayerId),
    [activePlayers, currentPlayerId]
  );

  const handleSelect = (player: Player) => {
    onSelectPlayer(player);
    sessionStorage.setItem("chat_target_id",player.id)
    // איפוס מונה לוקאלי + סימון לשרת אם יש לא־נקראו
    if (onMarkRead && (unreadCounts[player.id] || 0) > 0) {
      onMarkRead(player.id);
    }
  };

  // תגית "unread" ליד שם השחקן
  const UnreadBadge: React.FC<{ count: number }> = ({ count }) =>
    count > 0 ? (
      <span
        className="
          ml-2 inline-flex items-center justify-center
          min-w-[1.25rem] h-5 px-1.5
          text-[11px] font-semibold
          rounded-full bg-rose-600/90 text-white
          shadow shadow-rose-900/30
        "
        aria-label={`${count} unread`}
      >
        {count > 99 ? '99+' : count}
      </span>
    ) : null;

  return (
    <div className="w-80 bg-gradient-to-b from-slate-900 to-slate-800 border-r border-slate-700 flex flex-col">
      {/* Header */}
      <div className="p-6 border-b border-slate-700">
        <div className="flex items-center gap-3 mb-2">
          <div className="p-2 rounded-lg bg-gradient-to-r from-cyan-500 to-blue-500">
            <Users className="w-6 h-6 text-white" />
          </div>
        </div>
        <div className="flex items-baseline justify-between">
          <h2 className="text-xl font-bold text-white">Active Players</h2>
          <div className="text-sm text-slate-300">{activePlayers.length} online</div>
        </div>
      </div>

      {/* Players List */}
      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        {/* YOU (always on top) */}
        {me && (
          <div
            className="
              p-4 rounded-xl bg-slate-800 border border-slate-600
              cursor-default opacity-100
            "
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="relative">
                  <div className="w-10 h-10 rounded-full bg-gradient-to-r from-emerald-500 to-teal-500 flex items-center justify-center text-white font-bold">
                    {me.username?.charAt(0).toUpperCase()}
                  </div>
                  <div className={`absolute -bottom-1 -right-1 ${getStatusColor(me.status || 'online')}`}>
                    {getStatusIcon(me.status || 'online')}
                  </div>
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <span className="font-semibold text-white">{me.username}</span>
                    <span className="px-2 py-0.5 text-xs rounded-full bg-cyan-600/30 text-cyan-300 border border-cyan-500/40">
                      You
                    </span>
                  </div>
                  <div className="text-xs text-slate-300 capitalize">
                    {me.status || 'online'}
                    {me.level && <span className="ml-2">• Lvl {me.level}</span>}
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* OTHERS */}
        {others.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-48 text-slate-400">
            <Circle className="w-12 h-12 mb-3 opacity-50" />
            <p>No other players online</p>
          </div>
        ) : (
          others.map(player => {
            const isSelected = selectedPlayer?.id === player.id;
            const unread = unreadCounts[player.id] || 0;

            return (
              <button
                type="button"
                key={player.id}
                onClick={() => handleSelect(player)}
                className={`
                  w-full text-left p-4 rounded-xl transition-all duration-200 transform hover:scale-105
                  ${isSelected
                    ? 'bg-gradient-to-r from-cyan-600 to-blue-600 shadow-lg shadow-cyan-500/25'
                    : 'bg-slate-800 hover:bg-slate-700'
                  }
                  border border-slate-600 hover:border-cyan-400/50
                  focus:outline-none focus:ring-2 focus:ring-cyan-500/50
                `}
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="relative">
                      <div className="w-10 h-10 rounded-full bg-gradient-to-r from-purple-500 to-pink-500 flex items-center justify-center text-white font-bold">
                        {player.username?.charAt(0).toUpperCase()}
                      </div>
                      <div className={`absolute -bottom-1 -right-1 ${getStatusColor(player.status || 'online')}`}>
                        {getStatusIcon(player.status || 'online')}
                      </div>
                    </div>

                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-semibold text-white">{player.username}</span>
                        {player.level && player.level > 50 && <Crown className="w-4 h-4 text-yellow-400" />}
                        <UnreadBadge count={unread} />
                      </div>
                      <div className="text-xs text-slate-300 capitalize">
                        {player.status || 'online'}
                        {player.level && <span className="ml-2">• Lvl {player.level}</span>}
                      </div>
                    </div>
                  </div>
                </div>
              </button>
            );
          })
        )}
      </div>

      {/* Footer */}
      <div className="p-4 border-t border-slate-700">
        <div className="text-xs text-slate-400 text-center">🎮 Game Chat • Talk. Play. Enjoy.</div>
      </div>
    </div>
  );
};

export default Sidebar;

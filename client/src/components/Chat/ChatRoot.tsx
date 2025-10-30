import React, { useEffect, useState, useMemo } from "react";
import { X } from "lucide-react";
// import { useWebSocket } from "../../hooks/useWebSocket";
import { useSharedWebSocket } from "../../context/WebSocketProvider";
import Sidebar from "./Sidebar";
import ChatInterface from "./ChatInterface";
import CustomizationPanel from "./CustomizationPanel";
import type { ChatTheme } from "../../types";

export type LocalPlayer = {
  id: string;
  username?: string;
  email?: string;
  row: number;
  col: number;
  chunk_id?: string;
};

interface ChatRootProps {
  onClose?: () => void;
  playerId: string;                  // who I am
  currentChunkId?: string | null;    // my server-known chunk id
  playersInChunk: LocalPlayer[];     // live from VoxelGrid
}

const ChatRoot: React.FC<ChatRootProps> = ({
  onClose,
  playerId,
  currentChunkId,
  playersInChunk,
}) => {
  const {
    messages,
    selectedPlayer,
    sendMessage,
    selectPlayer,
    reactToMessage,
    deleteMessage,
    currentPlayerId, // we actually rely on the prop playerId for "me", but we keep this around for debugging if needed
    unreadCounts,
    markRead,
  } = useSharedWebSocket();

  // "me"
  const meId = playerId;

  // chunkId we think we're in
  const chunkId = currentChunkId ?? playersInChunk[0]?.chunk_id ?? "chunk_0_0";

  // locate my own record (row/col)
  const me = useMemo(() => {
    return playersInChunk.find((p) => p.id === meId) || null;
  }, [playersInChunk, meId]);

  // find nearest other player in this chunk to me
  const nearestLocal = useMemo(() => {
    if (!me) return null;
    let best: LocalPlayer | null = null;
    let bestD = Infinity;
    for (const p of playersInChunk) {
      if (p.id === me.id) continue;
      const d = Math.hypot(
        (p.row ?? 0) - (me.row ?? 0),
        (p.col ?? 0) - (me.col ?? 0)
      );
      if (d < bestD) {
        bestD = d;
        best = p;
      }
    }
    return best;
  }, [me, playersInChunk]);

  const nearestPlayerId = nearestLocal?.id;

  // convert playersInChunk → sidebar format
  const sidebarPlayers = useMemo(() => {
    return playersInChunk.map((p) => ({
      id: p.id,
      username: p.username ?? p.id,
      email: p.email ?? "",
      status: "online",
    }));
  }, [playersInChunk]);

  // Debug log
  useEffect(() => {
    console.log({
      meId,
      chunkId,
      nearestId: nearestPlayerId,
      playersShown: sidebarPlayers.map((p) => `${p.username}:${p.id}`),
    });
  }, [meId, chunkId, nearestPlayerId, sidebarPlayers]);

  // Auto-select nearest player on mount / when nearest changes
  useEffect(() => {
    if (!nearestLocal) return;
    if (!selectedPlayer || selectedPlayer.id !== nearestLocal.id) {
      selectPlayer({
        id: nearestLocal.id,
        username: nearestLocal.username ?? nearestLocal.id,
      } as any);
    }
  }, [nearestLocal, selectedPlayer, selectPlayer]);

  // Theme state (unchanged)
  const [showCustomization, setShowCustomization] = useState(false);
  const [currentTheme, setCurrentTheme] = useState<ChatTheme>({
    name: "Cyber Blue",
    primaryColor: "#0ea5e9",
    secondaryColor: "#06b6d4",
    accentColor: "#3b82f6",
    backgroundColor: "#0f172a",
    cardColor: "#1e293b",
    textColor: "#f8fafc",
  });

  return (
    <div
      className="relative flex h-full w-full overflow-hidden"
      style={{
        backgroundColor: currentTheme.backgroundColor,
        color: currentTheme.textColor,
      }}
    >
      {/* Sidebar with active players */}
      <Sidebar
        activePlayers={sidebarPlayers as any}
        nearestPlayerId={nearestPlayerId}
        selectedPlayer={selectedPlayer}
        onSelectPlayer={selectPlayer}
        currentPlayerId={meId}
        unreadCounts={unreadCounts}
        onMarkRead={markRead}
      />

      {/* Main Chat Area */}
      <div className="flex-1 h-full flex flex-col">
        <div className="px-4 py-3 border-b border-slate-700 flex items-center justify-between">
          <div className="font-semibold">Game Chat</div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setShowCustomization((v) => !v)}
              className="bg-slate-700 hover:bg-slate-600 px-3 py-1.5 rounded transition-all text-sm"
            >
              Theme
            </button>
            {onClose && (
              <button
                onClick={onClose}
                className="bg-slate-700 hover:bg-slate-600 p-2 rounded-full transition-all"
                title="Close chat"
              >
                <X size={18} />
              </button>
            )}
          </div>
        </div>

        <div className="flex-1 min-h-0">
          <ChatInterface
            messages={messages}
            selectedPlayer={selectedPlayer}
            currentPlayerId={meId}
            onSendMessage={(text, quoted) => {
              if (!selectedPlayer) return;
              if (selectedPlayer.id === meId) {
                alert("You can't chat with yourself.");
                return;
              }
              if (nearestPlayerId && selectedPlayer.id !== nearestPlayerId) {
                alert(
                  "You can only chat with the nearest player in your chunk."
                );
                return;
              }
              // this calls useWebSocket.sendMessage
              sendMessage(text, quoted, {
                chunkId,
              });
            }}
            onReactMessage={(messageId, reaction) =>
              reactToMessage(messageId, reaction)
            }
            onDeleteMessage={deleteMessage}
            playersInChunk={playersInChunk as any}
            nearestPlayerId={nearestPlayerId}
          />
        </div>
      </div>

      {showCustomization && (
        <CustomizationPanel
          currentTheme={currentTheme}
          themes={[currentTheme]}
          onThemeChange={setCurrentTheme}
          onClose={() => setShowCustomization(false)}
        />
      )}
    </div>
  );
};

export default ChatRoot;

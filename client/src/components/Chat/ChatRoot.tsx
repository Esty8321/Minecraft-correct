import React, { useEffect, useState, useMemo } from "react";
import { X } from "lucide-react";
import { useWebSocket } from "../../hooks/useWebSocket";
import Sidebar from "./Sidebar";
import ChatInterface from "./ChatInterface";
import CustomizationPanel from "./CustomizationPanel";
import type { ChatTheme } from "../../types";
export type LocalPlayer = {
  id: string;
  username: string;
  email: string;
  row: number;
  col: number;
  chunk_id: string;
};
const SEED_PLAYERS: LocalPlayer[] = [
  { id: "00000011", username: "Shira", email: "tamar48719@gmail.com", row: 3, col: 8, chunk_id: "chunk_0_0" },
  { id: "00000100", username: "AAA",   email: "AAA@gmail.com",        row: 5, col: 4, chunk_id: "chunk_0_0" }, // YOU
  { id: "00000101", username: "BBB",   email: "BBB@gmail.com",        row: 9, col: 6, chunk_id: "chunk_0_0" },
];
interface ChatRootProps {
  onClose?: () => void;
  playerId: string;                 // ← את זהות השחקן האמיתית מקבלים מבחוץ
  currentChunkId?: string | null;
}

const ChatRoot: React.FC<ChatRootProps> = ({ onClose, playerId, currentChunkId }) => {
  const {
    messages,
    selectedPlayer,
    sendMessage,
    selectPlayer,
    reactToMessage,
    deleteMessage,
    currentPlayerId,                // מגיע מה־WS (לא נשתמש בו כ"אני")
    unreadCounts,
    markRead,
  } = useWebSocket();

  // ====== זהות "אני" וקביעת צ'אנק ======
  const meId = playerId;            // ✅ תמיד אני = ה־prop שהגיע לקומפוננטה

  // רשומת המשתמש שלי מתוך הדאטה (אם קיימת)
  const myRec = useMemo(
    () => SEED_PLAYERS.find(p => p.id === meId) || null,
    [meId]
  );

  // ✅ קביעת chunkId: קודם מתוך הדאטה של המשתמש → ואז מה־prop → ואז ברירת מחדל
  const chunkId = (currentChunkId ?? myRec?.chunk_id ?? "chunk_0_0");

  // ====== שחקנים לצ'אנק הנוכחי (עם Fallback) ======
  const playersInChunkRaw = useMemo(
    () => SEED_PLAYERS.filter(p => p.chunk_id === chunkId),
    [chunkId]
  );

  // ✅ אם מסיבה כלשהי אין אף שחקן בצ'אנק (מיסמאץ'), מציגים את כל הדאטה כדי לא להיות במסך ריק
  const playersInChunk = playersInChunkRaw.length ? playersInChunkRaw : SEED_PLAYERS;

  const me = useMemo(
    () => playersInChunk.find(p => p.id === meId) || null,
    [playersInChunk, meId]
  );

  // ====== חישוב הקרוב ביותר מתוך הדאטה בלבד ======
  const nearestLocal = useMemo(() => {
    if (!me) return null;
    let best: typeof me | null = null;
    let bestD = Number.POSITIVE_INFINITY;
    for (const p of playersInChunk) {
      if (p.id === me.id) continue;
      const d = Math.hypot((p.row ?? 0) - (me.row ?? 0), (p.col ?? 0) - (me.col ?? 0));
      if (d < bestD) {
        bestD = d;
        best = p;
      }
    }
    return best;
  }, [me, playersInChunk]);

  const nearestPlayerId = nearestLocal?.id;

  // רשימת שחקנים ל־Sidebar (לא חייבת row/col)
  const localPlayers = useMemo(() => {
    return playersInChunk.map(p => ({
      id: p.id,
      username: p.username,
      email: (p as any).email,
      status: "online",
    }));
  }, [playersInChunk]);

  // דיבוג ידידותי
  useEffect(() => {
    console.log({
      meId,
      chunkId,
      myRecChunk: myRec?.chunk_id,
      nearestId: nearestPlayerId,
      playersShown: localPlayers.map(p => `${p.username}:${p.id}`)
    });
  }, [meId, chunkId, myRec, nearestPlayerId, localPlayers]);

  // ====== אתחול/תיקון בחירת הנמען ======
  useEffect(() => {
    if (!nearestLocal) return;
    if (!selectedPlayer || selectedPlayer.id !== nearestLocal.id) {
      // נבחר אוטומטית את הקרוב ביותר מהדאטה
      selectPlayer({ id: nearestLocal.id, username: nearestLocal.username } as any);
    }
  }, [nearestLocal, selectedPlayer, selectPlayer]);

  // ====== Theme (קיים) ======
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
      style={{ backgroundColor: currentTheme.backgroundColor, color: currentTheme.textColor }}
    >
      {/* Sidebar */}
      <Sidebar
        activePlayers={localPlayers as any}          // ← ממקור הדאטה הזמני בלבד
        nearestPlayerId={nearestPlayerId}            // ← הקרוב ביותר שחישבנו
        selectedPlayer={selectedPlayer}
        onSelectPlayer={selectPlayer}
        currentPlayerId={meId}                       // ← הזהות העקבית של "אני"
        unreadCounts={unreadCounts}
        onMarkRead={markRead}
      />

      {/* Main */}
      <div className="flex-1 h-full flex flex-col">
        <div className="px-4 py-3 border-b border-slate-700 flex items-center justify-between">
          <div className="font-semibold">Game Chat</div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setShowCustomization(v => !v)}
              className="bg-slate-700 hover:bg-slate-600 px-3 py-1.5 rounded transition-all text-sm"
            >
              Theme
            </button>
            {onClose && (
              <button onClick={onClose} className="bg-slate-700 hover:bg-slate-600 p-2 rounded-full transition-all" title="Close chat">
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
                alert("You can only chat with the nearest player in your chunk.");
                return;
              }
              sendMessage(text, quoted);
            }}
            onReactMessage={(messageId, reaction) => reactToMessage(messageId, reaction)}
            onDeleteMessage={deleteMessage}
            playersInChunk={playersInChunk as any}    // כולל row/col למודאל
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

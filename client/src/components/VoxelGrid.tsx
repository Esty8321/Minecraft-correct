import React, { useEffect, useState, useCallback, useMemo } from "react";
import { Wifi, WifiOff, Users, Gamepad2, MessageCircle, X, HelpCircle } from "lucide-react";
import { authStorage } from "../utils/auth";
import { MessageBubble } from "./MessageBubble";
import { MessageInput } from "./MessageInput";
import ChatRoot from "./Chat/ChatRoot";
import { InstructionsModal } from "./InstructionsModal";
import { useSharedWebSocket } from "../context/WebSocketProvider";

interface GameState {
  w: number;
  h: number;
  data: number[];
  chunk_id?: string;
}

type PlayerInChunk = {
  id: string;
  row: number;
  col: number;
};

const SYSTEM_TREASURE = "A player hid a treasure";

const QuoteToast: React.FC<{ text: string; onClose: () => void }> = ({
  text,
  onClose,
}) => {
  return (
    <div
      className="fixed bottom-8 left-1/2 -translate-x-1/2 z-[10001] max-w-[70vw] w-[680px] px-5 py-4
                 bg-white/95 text-slate-800 rounded-2xl shadow-2xl border border-slate-200
                 backdrop-blur-sm"
      role="status"
      aria-live="polite"
    >
      <div className="flex items-start gap-3">
        <div
          className="mt-0.5 h-full border-l-4 border-purple-400 rounded-full"
          aria-hidden
        />
        <div className="flex-1">
          <div className="text-sm uppercase tracking-wide text-slate-500">
            Message found here
          </div>
          <blockquote className="mt-1 text-lg leading-snug text-slate-900">
            "{text}"
          </blockquote>
        </div>
        <button
          onClick={onClose}
          className="shrink-0 inline-flex items-center justify-center rounded-full p-1
                     hover:bg-slate-100 transition"
          aria-label="Close"
          title="Close"
        >
          <X size={18} />
        </button>
      </div>
    </div>
  );
};

const VoxelGrid: React.FC = () => {
  const {isConnected, sendCommand} = useSharedWebSocket()

  const [gameState, setGameState] = useState<GameState | null>(null);
  const [playerCount, setPlayerCount] = useState(0);
  const [lastAction, setLastAction] = useState("");
  const [notice, setNotice] = useState<string | null>(null);
  const [showChat, setShowChat] = useState(false);
  const [showInstructions, setShowInstructions] = useState(false);

  const [players, setPlayers] = useState<PlayerInChunk[]>([]);

  const [showMessageInput, setShowMessageInput] = useState(false);
  const [currentMessage, setCurrentMessage] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  const [quoteText, setQuoteText] = useState<string | null>(null);

  useEffect(() => {
    if (!quoteText) return;
    const t = setTimeout(() => setQuoteText(null), 6000);
    return () => clearTimeout(t);
  }, [quoteText]);

  useEffect(() => {
    const handleGameUpdate = (ev: CustomEvent) => {
      const data = ev.detail;

      if (data.type === "matrix") {
        setGameState({
          w: data.w,
          h: data.h,
          data: data.data,
          chunk_id: data.chunk_id,
        });

        const newPlayers = Array.isArray(data.players) ? data.players : [];
        setPlayers(newPlayers);
        setPlayerCount(data.total_players ?? newPlayers.length);

        const newChunkId = String(data.chunk_id || "");
        if (newChunkId && newChunkId !== sessionStorage.getItem("current_chunk_id")) {
          sessionStorage.setItem("current_chunk_id", newChunkId);
          window.dispatchEvent(new Event("chunkChanged"));
        }
      }

      if (data.type === "announcement" && data.data?.text) {
        const text = String(data.data.text);

        if (text === SYSTEM_TREASURE) {
          setNotice(text);
          setTimeout(() => setNotice(null), 3000);
        } else {
          setQuoteText(text);
        }
      }

      if (data.type === "error") {
        if (data.code === "SPACE_OCCUPIED") {
          setError("You can't leave a message here — this spot is already taken.");
        } else {
          setError(String(data.message || "An error occurred."));
        }
        setShowMessageInput(false);
        setTimeout(() => setError(null), 3000);
      }
    };

    window.addEventListener("game-update", handleGameUpdate as EventListener);
    return () =>
      window.removeEventListener("game-update", handleGameUpdate as EventListener);
  }, []);

  const handleKeyPress = useCallback(
    (event: KeyboardEvent) => {
      if (!isConnected) return;

      const target = event.target as HTMLElement | null;
      const tag = target?.tagName?.toLowerCase();
      if (tag === "input" || tag === "textarea" || target?.isContentEditable) {
        return;
      }

      const key = event.key.toLowerCase();
      let action = "";

      switch (key) {
        case "arrowup":
        case "w":
          sendCommand("up");
          action = "Moved Up";
          break;
        case "arrowdown":
        case "s":
          sendCommand("down");
          action = "Moved Down";
          break;
        case "arrowleft":
        case "a":
          sendCommand("left");
          action = "Moved Left";
          break;
        case "arrowright":
        case "d":
          sendCommand("right");
          action = "Moved Right";
          break;
        case "m":
          setShowMessageInput(true);
          action = "Writing Message";
          break;
        case "c":
          sendCommand("c");
          action = "Color Changed";
          break;
      }

      if (action) {
        setLastAction(action);
        setTimeout(() => setLastAction(""), 1500);
        event.preventDefault();
      }
    },
    [isConnected, sendCommand]
  );

  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => handleKeyPress(e);
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [handleKeyPress]);

  const renderGrid = () => {
    if (!gameState) return null;

    const playerSet = new Set(players.map((p) => `${p.row},${p.col}`));
    const cells: JSX.Element[] = [];

    for (let r = 0; r < gameState.h; r++) {
      for (let c = 0; c < gameState.w; c++) {
        const i = r * gameState.w + c;
        const v = gameState.data[i];
        const isPlayer = (v & 1) === 1;
        const getBit = (x: number, bit: number) => (x >> bit) & 1;
        const get2 = (x: number, b0: number, b1: number) =>
          (getBit(x, b1) << 1) | getBit(x, b0);
        const r2 = get2(v, 2, 5);
        const g2 = get2(v, 3, 6);
        const b2 = get2(v, 4, 7);
        const blank = !isPlayer && r2 === 0 && g2 === 0 && b2 === 0;
        const map = [0, 85, 170, 255];
        const color = `rgb(${map[r2]}, ${map[g2]}, ${map[b2]})`;

        const isPlayersHere = playerSet.has(`${r},${c}`);
        cells.push(
          <div
            key={`${r}-${c}`}
            className={`voxel-cell ${isPlayer ? "voxel-player" : "voxel-empty"}`}
            style={{
              backgroundColor: blank ? "transparent" : color,
              outline: isPlayersHere ? "1px solid rgba(255,255,255,0.6)" : "none",
            }}
          />
        );
      }
    }

    return cells;
  };

  const enrichedPlayers = useMemo(() => {
    const chunkId =
      gameState?.chunk_id ?? sessionStorage.getItem("current_chunk_id") ?? null;
    return players.map((p) => ({
      ...p,
      username: p.id,
      email: "",
      chunk_id: chunkId || "",
    }));
  }, [players, gameState]);

  const myId = authStorage.getUser()?.id ?? "";

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900 text-white overflow-x-hidden">
      <div className="container mx-auto px-4 pt-8">
        <div className="text-center mb-6">
          <h1 className="text-4xl font-bold mb-2 bg-gradient-to-r from-blue-400 to-purple-400 bg-clip-text text-transparent">
            Voxel World
          </h1>
          <p className="text-slate-300 text-lg">
            A multiplayer voxel playground where colors come alive
          </p>
        </div>

        <div className="flex flex-wrap items-center justify-center gap-3 mb-6">
          <div
            className={`flex items-center gap-2 px-4 py-2 rounded-full ${
              isConnected ? "bg-green-500/20 text-green-300" : "bg-red-500/20 text-red-300"
            }`}
          >
            {isConnected ? <Wifi size={18} /> : <WifiOff size={18} />}
            <span className="font-medium">
              {isConnected ? "Connected" : "Connecting..."}
            </span>
          </div>

          <div className="flex items-center gap-2 px-4 py-2 rounded-full bg-blue-500/20 text-blue-300">
            <Users size={18} />
            <span className="font-medium">{playerCount} Players</span>
          </div>

          <button
            onClick={() => setShowInstructions(true)}
            className="flex items-center gap-2 px-4 py-2 rounded-full bg-amber-500/20 text-amber-300
                     hover:bg-amber-500/30 transition-all duration-200 transform hover:scale-105"
          >
            <HelpCircle size={18} />
            <span className="font-medium">How to Play</span>
          </button>

          {lastAction && (
            <div className="flex items-center gap-2 px-4 py-2 rounded-full bg-purple-500/20 text-purple-300 animate-pulse">
              <Gamepad2 size={18} />
              <span className="font-medium">{lastAction}</span>
            </div>
          )}
        </div>
      </div>

      <div className="flex flex-row-reverse min-h-[60vh]">
        <div
          className={`transition-all duration-500 ${
            showChat ? "w-3/4" : "w-full"
          } flex justify-center items-center px-4`}
        >
          {gameState ? (
            <div
              className="voxel-grid bg-slate-800/50 p-4 rounded-2xl backdrop-blur-sm border border-slate-700/50 shadow-2xl"
              style={{
                display: "grid",
                gridTemplateColumns: `repeat(${gameState.w}, 1fr)`,
                gap: "1px",
                maxWidth: "800px",
                aspectRatio: "1",
                width: "100%",
              }}
            >
              {renderGrid()}
            </div>
          ) : (
            <div className="flex items-center justify-center w-96 h-96 bg-slate-800/50 rounded-2xl backdrop-blur-sm border border-slate-700/50">
              <div className="text-center">
                <div className="animate-spin w-8 h-8 border-2 border-blue-400 border-t-transparent rounded-full mx-auto mb-4" />
                <p className="text-slate-400">Connecting to voxel world...</p>
              </div>
            </div>
          )}
        </div>

        <div
          className={`transition-all duration-500 ${
            showChat ? "w-1/4 opacity-100" : "w-0 opacity-0 pointer-events-none"
          } bg-slate-900 text-white shadow-2xl overflow-hidden border-l border-slate-800`}
        >
          {showChat && (
            <ChatRoot
              onClose={() => setShowChat(false)}
              playerId={myId}
              currentChunkId={
                gameState?.chunk_id ?? sessionStorage.getItem("current_chunk_id") ?? null
              }
              playersInChunk={enrichedPlayers}
            />
          )}
        </div>
      </div>

      <button
        onClick={() => setShowChat((prev) => !prev)}
        className="fixed top-6 right-6 bg-cyan-600 hover:bg-cyan-500 text-white p-3 rounded-full shadow-xl transition-all z-[10000]"
        title={showChat ? "Close Chat" : "Open Chat"}
      >
        {showChat ? <X size={22} /> : <MessageCircle size={22} />}
      </button>

      <div className="fixed bottom-4 left-4 text-sm text-slate-300 flex items-center gap-3 bg-slate-800/70 px-3 py-2 rounded-md backdrop-blur-sm border border-slate-700/50 shadow-lg">
        {isConnected ? (
          <Wifi className="text-green-400" size={16} />
        ) : (
          <WifiOff className="text-red-400" size={16} />
        )}
        <span>
          {isConnected ? "Connected" : "Disconnected"} • {playerCount} players
        </span>
      </div>

      {notice && (
        <div className="fixed top-4 left-1/2 -translate-x-1/2 bg-blue-50/90 text-blue-800 px-4 py-2 rounded-lg shadow-lg border border-blue-200">
          {notice}
        </div>
      )}

      {quoteText && <QuoteToast text={quoteText} onClose={() => setQuoteText(null)} />}

      {showMessageInput && (
        <MessageInput
          onSubmit={(content: string) => {
            sendCommand({ command: "m", content});
            setShowMessageInput(false);
          }}
          onClose={() => setShowMessageInput(false)}
        />
      )}

      {showInstructions && (
        <InstructionsModal onClose={() => setShowInstructions(false)} />
      )}

      {currentMessage && <MessageBubble message={currentMessage} />}
      {error && (
        <div className="fixed top-4 right-4 bg-red-50 text-red-600 px-4 py-3 rounded-lg shadow-lg border border-red-200">
          {error}
        </div>
      )}
    </div>
  );
};

export default VoxelGrid;

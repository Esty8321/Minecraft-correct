// import React, { useEffect, useState, useCallback, useRef } from "react";
// import { Wifi, WifiOff, Users, Gamepad2, Palette, MessageCircle, X } from "lucide-react";
// import { authStorage } from "../utils/auth";
// import { MessageBubble } from "./MessageBubble";
// import { MessageInput } from "./MessageInput";
// import ChatPanel from "./Chat/ChatPanel";
// const ENV_WS = (import.meta as any).env?.VITE_GAME_WS as string | undefined;

// interface GameState {
//   w: number;
//   h: number;
//   data: number[];
//   chunk_id?: string;
// }

// interface VoxelGridProps {
//   serverUrl?: string;
// }

// const VoxelGrid: React.FC<VoxelGridProps> = ({ serverUrl }) => {
//   const [gameState, setGameState] = useState<GameState | null>(null);
//   const [connected, setConnected] = useState(false);
//   const [playerCount, setPlayerCount] = useState(0);
//   const [lastAction, setLastAction] = useState<string>("");

//   const [showChat, setShowChat] = useState(false)
//   const wsRef = useRef<WebSocket | null>(null);
//   const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
//   const reconnectingRef = useRef<boolean>(false);

//   const [showMessageInput, setShowMessageInput] = useState(false);
//   const [currentMessage, setCurrentMessage] = useState<any>(null);
//   const [error, setError] = useState<string | null>(null);
//   const hideTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

//   const getWebSocketUrl = useCallback((): string => {
//     if (serverUrl && serverUrl.startsWith("ws")) return serverUrl;
//     if (ENV_WS && ENV_WS.startsWith("ws")) return ENV_WS;
//     const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
//     return `${proto}//${window.location.host}/game/ws`;
//   }, [serverUrl]);

//   const connectWebSocket = useCallback(() => {
//     if (
//       wsRef.current &&
//       (wsRef.current.readyState === WebSocket.OPEN ||
//         wsRef.current.readyState === WebSocket.CONNECTING)
//     ) {
//       return;
//     }

//     try {
//       const base = getWebSocketUrl();
//       const token = authStorage.getToken?.() ?? localStorage.getItem("token") ?? "";
//       if (!token) return;
//       const url = `${base}?token=${encodeURIComponent(token)}`;

//       const ws = new WebSocket(url);
//       wsRef.current = ws;

//       ws.onopen = () => {
//         setConnected(true);
//         try {
//           ws.send(JSON.stringify({ k: "whereami" }));
//         } catch {}
//       };

//       ws.onmessage = (event) => {
//         try {
//           const data = JSON.parse(event.data);
//           if (data.type === "matrix") {
//             setGameState({
//               w: data.w,
//               h: data.h,
//               data: data.data,
//               chunk_id: data.chunk_id,
//             });
//             if (Array.isArray(data.data)) {
//               const players = data.data.filter((cell: number) => (cell & 1) === 1);
//               setPlayerCount(players.length);
//             } else if (typeof data.total_players === "number") {
//               setPlayerCount(data.total_players);
//             }
//           } else if (data.type === "message" && data.data) {
//             setCurrentMessage(data.data);
//             if (hideTimerRef.current) clearTimeout(hideTimerRef.current);
//             hideTimerRef.current = setTimeout(() => setCurrentMessage(null), 5000);
//           } else if (data.type === "error" && data.code === "SPACE_OCCUPIED") {
//             setError("Oops! This spot already has a message! 📫");
//             setTimeout(() => setError(null), 3000);
//           }
//         } catch {}
//       };

//       ws.onclose = () => {
//         setConnected(false);
//         setGameState(null);
//         setPlayerCount(0);
//         if (!reconnectingRef.current) {
//           reconnectingRef.current = true;
//           reconnectTimeoutRef.current = setTimeout(() => {
//             reconnectingRef.current = false;
//             connectWebSocket();
//           }, 3000);
//         }
//       };

//       ws.onerror = () => setConnected(false);
//     } catch {
//       setConnected(false);
//     }
//   }, [getWebSocketUrl]);

//   const sendMessage = useCallback((message: any) => {
//     if (wsRef.current?.readyState === WebSocket.OPEN) {
//       wsRef.current.send(JSON.stringify(message));
//     }
//   }, []);

//   const handleKeyPress = useCallback(
//     (event: KeyboardEvent) => {
//       if (!connected) return;
//       const key = event.key.toLowerCase();
//       let action = "";
//       switch (key) {
//         case "arrowup":
//         case "w":
//           sendMessage({ k: "up" });
//           action = "Moved Up";
//           break;
//         case "arrowdown":
//         case "s":
//           sendMessage({ k: "down" });
//           action = "Moved Down";
//           break;
//         case "arrowleft":
//         case "a":
//           sendMessage({ k: "left" });
//           action = "Moved Left";
//           break;
//         case "arrowright":
//         case "d":
//           sendMessage({ k: "right" });
//           action = "Moved Right";
//           break;
//         case "m":
//           setShowMessageInput(true);
//           action = "Writing Message";
//           break;
//         case "c":
//           sendMessage({ k: "c" });
//           action = "Color Changed";
//           break;
//       }
//       if (action) {
//         setLastAction(action);
//         window.setTimeout(() => setLastAction(""), 2000);
//         event.preventDefault();
//       }
//     },
//     [connected, sendMessage]
//   );

//   useEffect(() => {
//     connectWebSocket();
//     return () => {
//       if (reconnectTimeoutRef.current) {
//         clearTimeout(reconnectTimeoutRef.current);
//         reconnectTimeoutRef.current = null;
//       }
//       if (hideTimerRef.current) {
//         clearTimeout(hideTimerRef.current);
//         hideTimerRef.current = null;
//       }
//       try {
//         wsRef.current?.close();
//         wsRef.current = null;
//       } catch {}
//     };
//   }, [connectWebSocket]);

//   useEffect(() => {
//     window.addEventListener("keydown", handleKeyPress);
//     return () => window.removeEventListener("keydown", handleKeyPress);
//   }, [handleKeyPress]);

//   const renderGrid = () => {
//     if (!gameState) return null;
//     const cells: JSX.Element[] = [];
//     for (let r = 0; r < gameState.h; r++) {
//       for (let c = 0; c < gameState.w; c++) {
//         const i = r * gameState.w + c;
//         const v = gameState.data[i];
//         const isPlayer = (v & 1) === 1;

//         const getBit = (x: number, bit: number) => (x >> bit) & 1;
//         const get2 = (x: number, b0: number, b1: number) => (getBit(x, b1) << 1) | getBit(x, b0);
//         const r2 = get2(v, 2, 5);
//         const g2 = get2(v, 3, 6);
//         const b2 = get2(v, 4, 7);
//         const blank = !isPlayer && r2 === 0 && g2 === 0 && b2 === 0;
//         const map = [0, 85, 170, 255];
//         const color = `rgb(${map[r2]}, ${map[g2]}, ${map[b2]})`;

//         cells.push(
//           <div
//             key={`${r}-${c}`}
//             className={`voxel-cell ${isPlayer ? "voxel-player" : "voxel-empty"}`}
//             style={{
//               backgroundColor: blank ? "transparent" : color,
//               outline: isPlayer ? "1px solid rgba(255,255,255,0.6)" : "none",
//             }}
//           />
//         );
//       }
//     }
//     return cells;
//   };

// return (
//     <div className="relative min-h-screen bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900 text-white overflow-hidden">
//       {/* GAME + CHAT SPLIT */}
//       <div className="flex h-screen">
//         {/* --- GAME SIDE --- */}
//         <div className={`transition-all duration-500 ${showChat ? "w-1/2" : "w-full"} flex justify-center items-center`}>
//           {gameState ? (
//             <div
//               className="voxel-grid bg-slate-800/50 p-4 rounded-2xl backdrop-blur-sm border border-slate-700/50 shadow-2xl"
//               style={{
//                 display: "grid",
//                 gridTemplateColumns: `repeat(${gameState.w}, 1fr)`,
//                 gap: "1px",
//                 maxWidth: "800px",
//                 aspectRatio: "1",
//               }}
//             >
//               {renderGrid()}
//             </div>
//           ) : (
//             <div className="text-slate-400">Connecting to voxel world...</div>
//           )}
//         </div>

//         {/* --- CHAT SIDE --- */}
//         <div
//           className={`transition-all duration-500 bg-gray-50 text-black ${
//             showChat ? "w-1/2 opacity-100" : "w-0 opacity-0 pointer-events-none"
//           } shadow-lg overflow-hidden`}
//         >
//           <ChatPanel />
//         </div>
//       </div>

//       {/* --- FLOAT BUTTON --- */}
//       <button
//         onClick={() => setShowChat((prev) => !prev)}
//         className="absolute top-6 right-6 bg-cyan-600 hover:bg-cyan-500 text-white p-3 rounded-full shadow-xl transition-all"
//         title={showChat ? "Close Chat" : "Open Chat"}
//       >
//         {showChat ? <X size={22} /> : <MessageCircle size={22} />}
//       </button>

//       {/* --- STATUS --- */}
//       <div className="absolute bottom-4 left-4 text-sm text-slate-300 flex items-center gap-3">
//         {connected ? <Wifi className="text-green-400" size={16} /> : <WifiOff className="text-red-400" size={16} />}
//         <span>{connected ? "Connected" : "Disconnected"} • {playerCount} players</span>
//       </div>

//       {/* --- MESSAGE INPUT / BUBBLES --- */}
//       {showMessageInput && (
//         <MessageInput
//           onSubmit={(content: string) => {
//             sendMessage({ k: "m", content });
//             setShowMessageInput(false);
//           }}
//           onClose={() => setShowMessageInput(false)}
//         />
//       )}

//       {currentMessage && <MessageBubble message={currentMessage} />}

//       {error && (
//         <div className="fixed top-4 right-4 bg-red-50 text-red-600 px-4 py-3 rounded-lg shadow-lg border border-red-200 animate-fade-in">
//           {error}
//         </div>
//       )}
//     </div>
//   );
// };

// export default VoxelGrid;



import React, { useEffect, useState, useCallback, useRef } from "react";
import {
  Wifi,
  WifiOff,
  MessageCircle,
  X
} from "lucide-react";
import { authStorage } from "../utils/auth";
import { MessageBubble } from "./MessageBubble";
import { MessageInput } from "./MessageInput";
import ChatRoot from "./Chat/ChatRoot"; // ✅ full chat app
const ENV_WS = (import.meta as any).env?.VITE_GAME_WS as string | undefined;

interface GameState {
  w: number;
  h: number;
  data: number[];
  chunk_id?: string;
}

interface VoxelGridProps {
  serverUrl?: string;
}

const VoxelGrid: React.FC<VoxelGridProps> = ({ serverUrl }) => {
  const [gameState, setGameState] = useState<GameState | null>(null);
  const [connected, setConnected] = useState(false);
  const [playerCount, setPlayerCount] = useState(0);
  const [lastAction, setLastAction] = useState<string>("");

  const [showChat, setShowChat] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const reconnectingRef = useRef<boolean>(false);

  const [showMessageInput, setShowMessageInput] = useState(false);
  const [currentMessage, setCurrentMessage] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const hideTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // ---------- WebSocket URL ----------
  const getWebSocketUrl = useCallback((): string => {
    if (serverUrl && serverUrl.startsWith("ws")) return serverUrl;
    if (ENV_WS && ENV_WS.startsWith("ws")) return ENV_WS;
    const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
    return `${proto}//${window.location.host}/game/ws`;
  }, [serverUrl]);

  // ---------- Connect WebSocket ----------
  const connectWebSocket = useCallback(() => {
    if (
      wsRef.current &&
      (wsRef.current.readyState === WebSocket.OPEN ||
        wsRef.current.readyState === WebSocket.CONNECTING)
    ) {
      return;
    }

    try {
      const base = getWebSocketUrl();
      const token = authStorage.getToken?.() ?? localStorage.getItem("token") ?? "";
      if (!token) return;
      const url = `${base}?token=${encodeURIComponent(token)}`;

      const ws = new WebSocket(url);
      wsRef.current = ws;

      ws.onopen = () => {
        setConnected(true);
        try {
          ws.send(JSON.stringify({ k: "whereami" }));
        } catch {}
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.type === "matrix") {
            setGameState({
              w: data.w,
              h: data.h,
              data: data.data,
              chunk_id: data.chunk_id,
            });
            if (Array.isArray(data.data)) {
              const players = data.data.filter((cell: number) => (cell & 1) === 1);
              setPlayerCount(players.length);
            } else if (typeof data.total_players === "number") {
              setPlayerCount(data.total_players);
            }
          } else if (data.type === "message" && data.data) {
            setCurrentMessage(data.data);
            if (hideTimerRef.current) clearTimeout(hideTimerRef.current);
            hideTimerRef.current = setTimeout(() => setCurrentMessage(null), 5000);
          } else if (data.type === "error" && data.code === "SPACE_OCCUPIED") {
            setError("Oops! This spot already has a message! 📫");
            setTimeout(() => setError(null), 3000);
          }
        } catch {}
      };

      ws.onclose = () => {
        setConnected(false);
        setGameState(null);
        setPlayerCount(0);
        if (!reconnectingRef.current) {
          reconnectingRef.current = true;
          reconnectTimeoutRef.current = setTimeout(() => {
            reconnectingRef.current = false;
            connectWebSocket();
          }, 3000);
        }
      };

      ws.onerror = () => setConnected(false);
    } catch {
      setConnected(false);
    }
  }, [getWebSocketUrl]);

  // ---------- Send Message ----------
  const sendMessage = useCallback((message: any) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(message));
    }
  }, []);

  // ---------- Keyboard Controls ----------
  const handleKeyPress = useCallback(
    (event: KeyboardEvent) => {
      if (!connected) return;
      const key = event.key.toLowerCase();
      let action = "";
      switch (key) {
        case "arrowup":
        case "w":
          sendMessage({ k: "up" });
          action = "Moved Up";
          break;
        case "arrowdown":
        case "s":
          sendMessage({ k: "down" });
          action = "Moved Down";
          break;
        case "arrowleft":
        case "a":
          sendMessage({ k: "left" });
          action = "Moved Left";
          break;
        case "arrowright":
        case "d":
          sendMessage({ k: "right" });
          action = "Moved Right";
          break;
        case "m":
          setShowMessageInput(true);
          action = "Writing Message";
          break;
        case "c":
          sendMessage({ k: "c" });
          action = "Color Changed";
          break;
      }
      if (action) {
        setLastAction(action);
        window.setTimeout(() => setLastAction(""), 2000);
        event.preventDefault();
      }
    },
    [connected, sendMessage]
  );

  // ---------- Lifecycle ----------
  useEffect(() => {
    connectWebSocket();
    return () => {
      if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current);
      if (hideTimerRef.current) clearTimeout(hideTimerRef.current);
      try {
        wsRef.current?.close();
        wsRef.current = null;
      } catch {}
    };
  }, [connectWebSocket]);

  useEffect(() => {
    window.addEventListener("keydown", handleKeyPress);
    return () => window.removeEventListener("keydown", handleKeyPress);
  }, [handleKeyPress]);

  // ---------- Render Voxel Grid ----------
  const renderGrid = () => {
    if (!gameState) return null;
    const cells: JSX.Element[] = [];
    for (let r = 0; r < gameState.h; r++) {
      for (let c = 0; c < gameState.w; c++) {
        const i = r * gameState.w + c;
        const v = gameState.data[i];
        const isPlayer = (v & 1) === 1;

        const getBit = (x: number, bit: number) => (x >> bit) & 1;
        const get2 = (x: number, b0: number, b1: number) => (getBit(x, b1) << 1) | getBit(x, b0);
        const r2 = get2(v, 2, 5);
        const g2 = get2(v, 3, 6);
        const b2 = get2(v, 4, 7);
        const blank = !isPlayer && r2 === 0 && g2 === 0 && b2 === 0;
        const map = [0, 85, 170, 255];
        const color = `rgb(${map[r2]}, ${map[g2]}, ${map[b2]})`;

        cells.push(
          <div
            key={`${r}-${c}`}
            className={`voxel-cell ${isPlayer ? "voxel-player" : "voxel-empty"}`}
            style={{
              backgroundColor: blank ? "transparent" : color,
              outline: isPlayer ? "1px solid rgba(255,255,255,0.6)" : "none",
            }}
          />
        );
      }
    }
    return cells;
  };

  // ---------- UI ----------
  return (
    <div className="relative min-h-screen bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900 text-white overflow-hidden">
      {/* MAIN LAYOUT */}
      <div className="flex h-screen">
        {/* --- GAME SIDE --- */}
        <div
          className={`transition-all duration-500 ${
            showChat ? "w-1/2" : "w-full"
          } flex justify-center items-center`}
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
              }}
            >
              {renderGrid()}
            </div>
          ) : (
            <div className="text-slate-400">Connecting to voxel world...</div>
          )}
        </div>

        {/* --- CHAT SIDE --- */}
        <div
          className={`transition-all duration-500 ${
            showChat ? "w-1/2 opacity-100" : "w-0 opacity-0 pointer-events-none"
          } bg-slate-900 text-white shadow-2xl overflow-hidden border-l border-slate-800`}
        >
          {showChat && (
            <div className="h-full w-full relative">
              <ChatRoot onClose={() => setShowChat(false)} />
            </div>
          )}
        </div>
      </div>

      {/* --- FLOAT BUTTON --- */}
      <button
        onClick={() => setShowChat((prev) => !prev)}
        className="absolute top-6 right-6 bg-cyan-600 hover:bg-cyan-500 text-white p-3 rounded-full shadow-xl transition-all"
        title={showChat ? "Close Chat" : "Open Chat"}
      >
        {showChat ? <X size={22} /> : <MessageCircle size={22} />}
      </button>

      {/* --- STATUS --- */}
      <div className="absolute bottom-4 left-4 text-sm text-slate-300 flex items-center gap-3">
        {connected ? (
          <Wifi className="text-green-400" size={16} />
        ) : (
          <WifiOff className="text-red-400" size={16} />
        )}
        <span>
          {connected ? "Connected" : "Disconnected"} • {playerCount} players
        </span>
      </div>

      {/* --- MESSAGE INPUT --- */}
      {showMessageInput && (
        <MessageInput
          onSubmit={(content: string) => {
            sendMessage({ k: "m", content });
            setShowMessageInput(false);
          }}
          onClose={() => setShowMessageInput(false)}
        />
      )}

      {/* --- MESSAGE BUBBLE --- */}
      {currentMessage && <MessageBubble message={currentMessage} />}

      {/* --- ERROR POPUP --- */}
      {error && (
        <div className="fixed top-4 right-4 bg-red-50 text-red-600 px-4 py-3 rounded-lg shadow-lg border border-red-200 animate-fade-in">
          {error}
        </div>
      )}
    </div>
  );
};

export default VoxelGrid;

// import React, { useEffect, useState, useCallback, useRef } from "react";
// import { Wifi, WifiOff, Users, Gamepad2, Palette, MessageCircle } from "lucide-react";
// import { authStorage } from "../utils/auth";
// import { MessageBubble } from "./MessageBubble";
// import { MessageInput } from "./MessageInput";

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
//   const [notice, setNotice] = useState<string | null>(null);

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
//           else if (data.type === "announcement" && data.data?.text) {
//             setNotice(String(data.data.text));
//            setTimeout(() => setNotice(null), 3000);
//         }

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

//   return (
//     <div className="min-h-screen bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900 text-white">
//       <div className="container mx-auto px-4 py-8">
//         <div className="text-center mb-8">
//           <h1 className="text-4xl font-bold mb-4 bg-gradient-to-r from-blue-400 to-purple-400 bg-clip-text text-transparent">
//             Voxel World
//           </h1>
//           <p className="text-slate-300 text-lg">A multiplayer voxel playground where colors come alive</p>
//         </div>
        
//         {notice && (
//           <div className="fixed top-4 left-1/2 -translate-x-1/2 z-50 bg-blue-50 text-blue-700 px-4 py-3 rounded-lg shadow-lg border border-blue-200">
//             {notice}
//           </div>
//        )}
//         <div className="flex justify-center items-center gap-6 mb-8">
//           <div
//             className={`flex items-center gap-2 px-4 py-2 rounded-full ${
//               connected ? "bg-green-500/20 text-green-300" : "bg-red-500/20 text-red-300"
//             }`}
//           >
//             {connected ? <Wifi size={18} /> : <WifiOff size={18} />}
//             <span className="font-medium">{connected ? "Connected" : "Connecting..."}</span>
//           </div>

//           <div className="flex items-center gap-2 px-4 py-2 rounded-full bg-blue-500/20 text-blue-300">
//             <Users size={18} />
//             <span className="font-medium">{playerCount} Players</span>
//           </div>

//           {lastAction && (
//             <div className="flex items-center gap-2 px-4 py-2 rounded-full bg-purple-500/20 text-purple-300 animate-pulse">
//               <Gamepad2 size={18} />
//               <span className="font-medium">{lastAction}</span>
//             </div>
//           )}
//         </div>

//         <div className="flex justify-center mb-8">
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
//             <div className="flex items-center justify-center w-96 h-96 bg-slate-800/50 rounded-2xl backdrop-blur-sm border border-slate-700/50">
//               <div className="text-center">
//                 <div className="animate-spin w-8 h-8 border-2 border-blue-400 border-t-transparent rounded-full mx-auto mb-4" />
//                 <p className="text-slate-400">Connecting to voxel world...</p>
//               </div>
//             </div>
//           )}
//         </div>

//         {showMessageInput && (
//           <MessageInput
//             onSubmit={(content: string) => {
//               sendMessage({ k: "m", content });
//               setShowMessageInput(false);
//             }}
//             onClose={() => setShowMessageInput(false)}
//           />
//         )}

//         {currentMessage && <MessageBubble message={currentMessage} />}

//         {error && (
//           <div className="fixed top-4 right-4 bg-red-50 text-red-600 px-4 py-3 rounded-lg shadow-lg border border-red-200 animate-fade-in">
//             {error}
//           </div>
//         )}

//         <div className="max-w-2xl mx-auto">
//           <h2 className="text-2xl font-semibold mb-6 text-center flex items-center justify-center gap-2">
//             <Gamepad2 className="text-purple-400" />
//             Controls
//           </h2>

//           <div className="grid md:grid-cols-2 gap-6">
//             <div className="bg-slate-800/50 p-6 rounded-xl backdrop-blur-sm border border-slate-700/50">
//               <h3 className="text-lg font-semibold mb-4 text-blue-300">Movement</h3>
//               <div className="space-y-2 text-slate-300">
//                 <p>
//                   <kbd className="px-2 py-1 bg-slate-700 rounded text-xs">↑</kbd>{" "}
//                   <kbd className="px-2 py-1 bg-slate-700 rounded text-xs">W</kbd> Move Up
//                 </p>
//                 <p>
//                   <kbd className="px-2 py-1 bg-slate-700 rounded text-xs">↓</kbd>{" "}
//                   <kbd className="px-2 py-1 bg-slate-700 rounded text-xs">S</kbd> Move Down
//                 </p>
//                 <p>
//                   <kbd className="px-2 py-1 bg-slate-700 rounded text-xs">←</kbd>{" "}
//                   <kbd className="px-2 py-1 bg-slate-700 rounded text-xs">A</kbd> Move Left
//                 </p>
//                 <p>
//                   <kbd className="px-2 py-1 bg-slate-700 rounded text-xs">→</kbd>{" "}
//                   <kbd className="px-2 py-1 bg-slate-700 rounded text-xs">D</kbd> Move Right
//                 </p>
//               </div>
//             </div>

//             <div className="bg-slate-800/50 p-6 rounded-xl backdrop-blur-sm border border-slate-700/50">
//               <h3 className="text-lg font-semibold mb-4 text-purple-300 flex items-center gap-2">
//                 <Palette size={18} />
//                 Colors
//               </h3>
//               <div className="space-y-2 text-slate-300">
//                 <p>
//                   <kbd className="px-2 py-1 bg-slate-700 rounded text-xs">C</kbd> Cycle Color
//                 </p>
//                 <p className="text-sm text-slate-400 mt-2">
//                   Press C to cycle through 64 different color combinations
//                 </p>
//               </div>
//             </div>
//           </div>

//           <div className="grid md:grid-cols-2 gap-6 mt-6">
//             <div className="bg-slate-800/50 p-6 rounded-xl backdrop-blur-sm border border-slate-700/50">
//               <h3 className="text-lg font-semibold mb-4 text-purple-300 flex items-center gap-2">
//                 <MessageCircle size={18} />
//                 Messages
//               </h3>
//               <div className="space-y-2 text-slate-300">
//                 <p>
//                   <kbd className="px-2 py-1 bg-slate-700 rounded text-xs">M</kbd> Write Message
//                 </p>
//                 <p className="text-sm text-slate-400 mt-2">
//                   Press M to leave a message at your current position
//                 </p>
//               </div>
//             </div>
//           </div>
//         </div>

//         <div className="text-center mt-12 text-slate-400" />
//       </div>
//     </div>
//   );
// };

// export default VoxelGrid;
import React, { useEffect, useState, useCallback, useRef } from "react";
import { Wifi, WifiOff, Users, Gamepad2, Palette, MessageCircle } from "lucide-react";
import { authStorage } from "../utils/auth";
import { MessageBubble } from "./MessageBubble";
import { MessageInput } from "./MessageInput";

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
  const [notice, setNotice] = useState<string | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const reconnectingRef = useRef<boolean>(false);

  const [showMessageInput, setShowMessageInput] = useState(false);
  const [currentMessage, setCurrentMessage] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const hideTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const getWebSocketUrl = useCallback((): string => {
    if (serverUrl && serverUrl.startsWith("ws")) return serverUrl;
    if (ENV_WS && ENV_WS.startsWith("ws")) return ENV_WS;
    const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
    return `${proto}//${window.location.host}/game/ws`;
  }, [serverUrl]);

  const connectWebSocket = useCallback(() => {
    if (wsRef.current && (wsRef.current.readyState === WebSocket.OPEN || wsRef.current.readyState === WebSocket.CONNECTING)) {
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
        try { ws.send(JSON.stringify({ k: "whereami" })); } catch {}
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.type === "matrix") {
            setGameState({ w: data.w, h: data.h, data: data.data, chunk_id: data.chunk_id });
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
          } else if (data.type === "announcement" && data.data?.text) {
            setNotice(String(data.data.text));
            setTimeout(() => setNotice(null), 3000);
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

  const sendMessage = useCallback((message: any) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(message));
    }
  }, []);

  const handleKeyPress = useCallback(
    (event: KeyboardEvent) => {
      if (!connected) return;

      if (showMessageInput) {
        if (event.key === "Escape") {
          setShowMessageInput(false);
          event.preventDefault();
        }
        return;
      }

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
    [connected, sendMessage, showMessageInput]
  );

  useEffect(() => {
    connectWebSocket();
    return () => {
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
        reconnectTimeoutRef.current = null;
      }
      if (hideTimerRef.current) {
        clearTimeout(hideTimerRef.current);
        hideTimerRef.current = null;
      }
      try {
        wsRef.current?.close();
        wsRef.current = null;
      } catch {}
    };
  }, [connectWebSocket]);

  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => handleKeyPress(e);
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [handleKeyPress]);

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

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900 text-white">
      <div className="container mx-auto px-4 py-8">
        <div className="text-center mb-8">
          <h1 className="text-4xl font-bold mb-4 bg-gradient-to-r from-blue-400 to-purple-400 bg-clip-text text-transparent">
            Voxel World
          </h1>
          <p className="text-slate-300 text-lg">A multiplayer voxel playground where colors come alive</p>
        </div>

        {notice && (
          <div className="fixed top-4 left-1/2 -translate-x-1/2 z-50 bg-blue-50 text-blue-700 px-4 py-3 rounded-lg shadow-lg border border-blue-200">
            {notice}
          </div>
        )}

        <div className="flex justify-center items-center gap-6 mb-8">
          <div className={`flex items-center gap-2 px-4 py-2 rounded-full ${connected ? "bg-green-500/20 text-green-300" : "bg-red-500/20 text-red-300"}`}>
            {connected ? <Wifi size={18} /> : <WifiOff size={18} />}
            <span className="font-medium">{connected ? "Connected" : "Connecting..."}</span>
          </div>

          <div className="flex items-center gap-2 px-4 py-2 rounded-full bg-blue-500/20 text-blue-300">
            <Users size={18} />
            <span className="font-medium">{playerCount} Players</span>
          </div>

          {lastAction && (
            <div className="flex items-center gap-2 px-4 py-2 rounded-full bg-purple-500/20 text-purple-300 animate-pulse">
              <Gamepad2 size={18} />
              <span className="font-medium">{lastAction}</span>
            </div>
          )}
        </div>

        <div className="flex justify-center mb-8">
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
            <div className="flex items-center justify-center w-96 h-96 bg-slate-800/50 rounded-2xl backdrop-blur-sm border border-slate-700/50">
              <div className="text-center">
                <div className="animate-spin w-8 h-8 border-2 border-blue-400 border-t-transparent rounded-full mx-auto mb-4" />
                <p className="text-slate-400">Connecting to voxel world...</p>
              </div>
            </div>
          )}
        </div>

        {showMessageInput && (
          <MessageInput
            onSubmit={(content: string) => {
              sendMessage({ k: "m", content });
              setShowMessageInput(false);
            }}
            onClose={() => setShowMessageInput(false)}
          />
        )}

        {currentMessage && <MessageBubble message={currentMessage} />}

        {error && (
          <div className="fixed top-4 right-4 bg-red-50 text-red-600 px-4 py-3 rounded-lg shadow-lg border border-red-200 animate-fade-in">
            {error}
          </div>
        )}

        <div className="max-w-2xl mx-auto">
          <h2 className="text-2xl font-semibold mb-6 text-center flex items-center justify-center gap-2">
            <Gamepad2 className="text-purple-400" />
            Controls
          </h2>

          <div className="grid md:grid-cols-2 gap-6">
            <div className="bg-slate-800/50 p-6 rounded-xl backdrop-blur-sm border border-slate-700/50">
              <h3 className="text-lg font-semibold mb-4 text-blue-300">Movement</h3>
              <div className="space-y-2 text-slate-300">
                <p>
                  <kbd className="px-2 py-1 bg-slate-700 rounded text-xs">↑</kbd>{" "}
                  <kbd className="px-2 py-1 bg-slate-700 rounded text-xs">W</kbd> Move Up
                </p>
                <p>
                  <kbd className="px-2 py-1 bg-slate-700 rounded text-xs">↓</kbd>{" "}
                  <kbd className="px-2 py-1 bg-slate-700 rounded text-xs">S</kbd> Move Down
                </p>
                <p>
                  <kbd className="px-2 py-1 bg-slate-700 rounded text-xs">←</kbd>{" "}
                  <kbd className="px-2 py-1 bg-slate-700 rounded text-xs">A</kbd> Move Left
                </p>
                <p>
                  <kbd className="px-2 py-1 bg-slate-700 rounded text-xs">→</kbd>{" "}
                  <kbd className="px-2 py-1 bg-slate-700 rounded text-xs">D</kbd> Move Right
                </p>
              </div>
            </div>

            <div className="bg-slate-800/50 p-6 rounded-xl backdrop-blur-sm border border-slate-700/50">
              <h3 className="text-lg font-semibold mb-4 text-purple-300 flex items-center gap-2">
                <Palette size={18} />
                Colors
              </h3>
              <div className="space-y-2 text-slate-300">
                <p>
                  <kbd className="px-2 py-1 bg-slate-700 rounded text-xs">C</kbd> Cycle Color
                </p>
                <p className="text-sm text-slate-400 mt-2">Press C to cycle through 64 different color combinations</p>
              </div>
            </div>
          </div>

          <div className="grid md:grid-cols-2 gap-6 mt-6">
            <div className="bg-slate-800/50 p-6 rounded-xl backdrop-blur-sm border border-slate-700/50">
              <h3 className="text-lg font-semibold mb-4 text-purple-300 flex items-center gap-2">
                <MessageCircle size={18} />
                Messages
              </h3>
              <div className="space-y-2 text-slate-300">
                <p>
                  <kbd className="px-2 py-1 bg-slate-700 rounded text-xs">M</kbd> Write Message
                </p>
                <p className="text-sm text-slate-400 mt-2">Press M to leave a message at your current position</p>
              </div>
            </div>
          </div>
        </div>

        <div className="text-center mt-12 text-slate-400" />
      </div>
    </div>
  );
};

export default VoxelGrid;

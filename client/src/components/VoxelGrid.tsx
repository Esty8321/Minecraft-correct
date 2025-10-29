// import React, { useEffect, useState, useCallback } from "react";
// import {
//   Wifi,
//   WifiOff,
//   Users,
//   Gamepad2,
//   Palette,
//   MessageCircle,
//   X,
// } from "lucide-react";
// import { authStorage } from "../utils/auth";
// import { MessageBubble } from "./MessageBubble";
// import { MessageInput } from "./MessageInput";
// import ChatRoot from "./Chat/ChatRoot";
// import { useWebSocket } from "../hooks/useWebSocket"; // ✅ shared socket hook

// interface GameState {
//   w: number;
//   h: number;
//   data: number[];
//   chunk_id?: string;
// }

// const VoxelGrid: React.FC = () => {
//   const { isConnected, sendCommand } = useWebSocket(); // ✅ shared WebSocket
//   const [gameState, setGameState] = useState<GameState | null>(null);
//   const [playerCount, setPlayerCount] = useState(0);
//   const [lastAction, setLastAction] = useState("");
//   const [notice, setNotice] = useState<string | null>(null);
//   const [showChat, setShowChat] = useState(false);
//   const [players, setPlayers] = useState<
//     Array<{ id: string; row: number; col: number }>
//   >([]);
//   const [showMessageInput, setShowMessageInput] = useState(false);
//   const [currentMessage, setCurrentMessage] = useState<any>(null);
//   const [error, setError] = useState<string | null>(null);

//   // === Listen to game updates from useWebSocket ===
//   useEffect(() => {
//     const handleGameUpdate = (ev: CustomEvent) => {
//       const data = ev.detail;

//       if (data.type === "matrix") {
//         setGameState({
//           w: data.w,
//           h: data.h,
//           data: data.data,
//           chunk_id: data.chunk_id,
//         });

//         const newPlayers = Array.isArray(data.players) ? data.players : [];
//         setPlayers(newPlayers);
//         setPlayerCount(data.total_players ?? newPlayers.length);

//         // track chunk
//         const newChunkId = String(data.chunk_id || "");
//         if (newChunkId && newChunkId !== sessionStorage.getItem("current_chunk_id")) {
//           sessionStorage.setItem("current_chunk_id", newChunkId);
//           window.dispatchEvent(new Event("chunkChanged"));
//         }
//       }

//       if (data.type === "announcement" && data.data?.text) {
//         setNotice(String(data.data.text));
//         setTimeout(() => setNotice(null), 3000);
//       }
//     };

//     window.addEventListener("game-update", handleGameUpdate as EventListener);
//     return () =>
//       window.removeEventListener("game-update", handleGameUpdate as EventListener);
//   }, []);

//   // === Handle key presses ===
//   const handleKeyPress = useCallback(
//     (event: KeyboardEvent) => {
//       if (!isConnected) return;

//       const key = event.key.toLowerCase();
//       let action = "";

//       switch (key) {
//         case "arrowup":
//         case "w":
//           sendCommand("up");
//           action = "Moved Up";
//           break;
//         case "arrowdown":
//         case "s":
//           sendCommand("down");
//           action = "Moved Down";
//           break;
//         case "arrowleft":
//         case "a":
//           sendCommand("left");
//           action = "Moved Left";
//           break;
//         case "arrowright":
//         case "d":
//           sendCommand("right");
//           action = "Moved Right";
//           break;
//         case "m":
//           setShowMessageInput(true);
//           action = "Writing Message";
//           break;
//         case "c":
//           sendCommand("c");
//           action = "Color Changed";
//           break;
//       }

//       if (action) {
//         setLastAction(action);
//         setTimeout(() => setLastAction(""), 1500);
//         event.preventDefault();
//       }
//     },
//     [isConnected, sendCommand]
//   );

//   useEffect(() => {
//     const onKeyDown = (e: KeyboardEvent) => handleKeyPress(e);
//     window.addEventListener("keydown", onKeyDown);
//     return () => window.removeEventListener("keydown", onKeyDown);
//   }, [handleKeyPress]);

//   // === Render the voxel grid ===
//   const renderGrid = () => {
//     if (!gameState) return null;

//     const playerSet = new Set(players.map((p) => `${p.row},${p.col}`));
//     const cells: JSX.Element[] = [];

//     for (let r = 0; r < gameState.h; r++) {
//       for (let c = 0; c < gameState.w; c++) {
//         const i = r * gameState.w + c;
//         const v = gameState.data[i];
//         const isPlayer = (v & 1) === 1;
//         const getBit = (x: number, bit: number) => (x >> bit) & 1;
//         const get2 = (x: number, b0: number, b1: number) =>
//           (getBit(x, b1) << 1) | getBit(x, b0);
//         const r2 = get2(v, 2, 5);
//         const g2 = get2(v, 3, 6);
//         const b2 = get2(v, 4, 7);
//         const blank = !isPlayer && r2 === 0 && g2 === 0 && b2 === 0;
//         const map = [0, 85, 170, 255];
//         const color = `rgb(${map[r2]}, ${map[g2]}, ${map[b2]})`;

//         const isPlayersHere = playerSet.has(`${r},${c}`);
//         cells.push(
//           <div
//             key={`${r}-${c}`}
//             className={`voxel-cell ${isPlayer ? "voxel-player" : "voxel-empty"}`}
//             style={{
//               backgroundColor: blank ? "transparent" : color,
//               outline: isPlayersHere
//                 ? "1px solid rgba(255,255,255,0.6)"
//                 : "none",
//             }}
//           />
//         );
//       }
//     }

//     return cells;
//   };

//   return (
//     <div className="min-h-screen bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900 text-white overflow-x-hidden">
//       {/* Header */}
//       <div className="container mx-auto px-4 pt-8">
//         <div className="text-center mb-6">
//           <h1 className="text-4xl font-bold mb-2 bg-gradient-to-r from-blue-400 to-purple-400 bg-clip-text text-transparent">
//             Voxel World
//           </h1>
//           <p className="text-slate-300 text-lg">
//             A multiplayer voxel playground where colors come alive
//           </p>
//         </div>

//         <div className="flex flex-wrap items-center justify-center gap-3 mb-6">
//           <div
//             className={`flex items-center gap-2 px-4 py-2 rounded-full ${
//               isConnected
//                 ? "bg-green-500/20 text-green-300"
//                 : "bg-red-500/20 text-red-300"
//             }`}
//           >
//             {isConnected ? <Wifi size={18} /> : <WifiOff size={18} />}
//             <span className="font-medium">
//               {isConnected ? "Connected" : "Connecting..."}
//             </span>
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
//       </div>

//       {/* Grid + Chat */}
//       <div className="flex flex-row-reverse min-h-[60vh]">
//         <div
//           className={`transition-all duration-500 ${
//             showChat ? "w-3/4" : "w-full"
//           } flex justify-center items-center px-4`}
//         >
//           {gameState ? (
//             <div
//               className="voxel-grid bg-slate-800/50 p-4 rounded-2xl backdrop-blur-sm border border-slate-700/50 shadow-2xl"
//               style={{
//                 display: "grid",
//                 gridTemplateColumns: `repeat(${gameState.w}, 1fr)`,
//                 gap: "1px",
//                 maxWidth: "800px",
//                 aspectRatio: "1",
//                 width: "100%",
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

//         {/* Chat panel */}
//         <div
//           className={`transition-all duration-500 ${
//             showChat
//               ? "w-1/4 opacity-100"
//               : "w-0 opacity-0 pointer-events-none"
//           } bg-slate-900 text-white shadow-2xl overflow-hidden border-l border-slate-800`}
//         >
//           {showChat && (
//             <ChatRoot
//               onClose={() => setShowChat(false)}
//               playerId={authStorage.getUser()?.id ?? ""}
//               currentChunkId={
//                 gameState?.chunk_id ??
//                 sessionStorage.getItem("current_chunk_id") ??
//                 null
//               }
//               // PlayerInChunk = {players}//??see how can I add it here
//             />
//           )}
//         </div>
//       </div>

//       {/* Floating chat toggle */}
//       <button
//         onClick={() => setShowChat((prev) => !prev)}
//         className="fixed top-6 right-6 bg-cyan-600 hover:bg-cyan-500 text-white p-3 rounded-full shadow-xl transition-all z-[10000]"
//         title={showChat ? "Close Chat" : "Open Chat"}
//       >
//         {showChat ? <X size={22} /> : <MessageCircle size={22} />}
//       </button>

//       {/* Notifications */}
//       <div className="fixed bottom-4 left-4 text-sm text-slate-300 flex items-center gap-3 bg-slate-800/70 px-3 py-2 rounded-md backdrop-blur-sm border border-slate-700/50 shadow-lg">
//         {isConnected ? (
//           <Wifi className="text-green-400" size={16} />
//         ) : (
//           <WifiOff className="text-red-400" size={16} />
//         )}
//         <span>
//           {isConnected ? "Connected" : "Disconnected"} • {playerCount} players
//         </span>
//       </div>

//       {notice && (
//         <div className="fixed top-4 left-1/2 -translate-x-1/2 bg-blue-50/90 text-blue-800 px-4 py-2 rounded-lg shadow-lg border border-blue-200">
//           {notice}
//         </div>
//       )}

//       {showMessageInput && (
//         <MessageInput
//           onSubmit={(content: string) => {
//             sendCommand(JSON.stringify({ command: "m", content }));
//             setShowMessageInput(false);
//           }}
//           onClose={() => setShowMessageInput(false)}
//         />
//       )}

//       {currentMessage && <MessageBubble message={currentMessage} />}
//       {error && (
//         <div className="fixed top-4 right-4 bg-red-50 text-red-600 px-4 py-3 rounded-lg shadow-lg border border-red-200">
//           {error}
//         </div>
//       )}
//     </div>
//   );
// };

// export default VoxelGrid;


import React, { useEffect, useState, useCallback, useMemo } from "react";
import {
  Wifi,
  WifiOff,
  Users,
  Gamepad2,
  MessageCircle,
  X,
} from "lucide-react";
import { authStorage } from "../utils/auth";
import { MessageBubble } from "./MessageBubble";
import { MessageInput } from "./MessageInput";
import ChatRoot from "./Chat/ChatRoot";
import { useWebSocket } from "../hooks/useWebSocket";

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
  // (no username from server yet, we’ll synthesize below)
};

const VoxelGrid: React.FC = () => {
  const { isConnected, sendCommand } = useWebSocket(); // shared socket (game + chat)
  const [gameState, setGameState] = useState<GameState | null>(null);
  const [playerCount, setPlayerCount] = useState(0);
  const [lastAction, setLastAction] = useState("");
  const [notice, setNotice] = useState<string | null>(null);
  const [showChat, setShowChat] = useState(false);

  const [players, setPlayers] = useState<PlayerInChunk[]>([]);

  const [showMessageInput, setShowMessageInput] = useState(false);
  const [currentMessage, setCurrentMessage] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  // Listen to game updates coming from useWebSocket
  useEffect(() => {
    const handleGameUpdate = (ev: CustomEvent) => {
      const data = ev.detail;

      if (data.type === "matrix") {
        // world snapshot
        setGameState({
          w: data.w,
          h: data.h,
          data: data.data,
          chunk_id: data.chunk_id,
        });

        // players in this chunk come from server payload
        const newPlayers = Array.isArray(data.players) ? data.players : [];
        setPlayers(newPlayers);
        setPlayerCount(data.total_players ?? newPlayers.length);

        // track current chunk for me
        const newChunkId = String(data.chunk_id || "");
        if (
          newChunkId &&
          newChunkId !== sessionStorage.getItem("current_chunk_id")
        ) {
          sessionStorage.setItem("current_chunk_id", newChunkId);
          window.dispatchEvent(new Event("chunkChanged"));
        }
      }

      if (data.type === "announcement" && data.data?.text) {
        setNotice(String(data.data.text));
        setTimeout(() => setNotice(null), 3000);
      }
    };

    window.addEventListener("game-update", handleGameUpdate as EventListener);
    return () =>
      window.removeEventListener(
        "game-update",
        handleGameUpdate as EventListener
      );
  }, []);

  // send WASD/arrow/m/c to server
  const handleKeyPress = useCallback(
    (event: KeyboardEvent) => {
      if (!isConnected) return;

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
          // world scroll message mode
          setShowMessageInput(true);
          action = "Writing Message";
          break;
        case "c":
          sendCommand("c"); // color++
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

  // grid renderer (voxel + highlighting where players are)
  const renderGrid = () => {
    if (!gameState) return null;

    const occupied = new Set(players.map((p) => `${p.row},${p.col}`));
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
        const palette = [0, 85, 170, 255];
        const color = `rgb(${palette[r2]}, ${palette[g2]}, ${palette[b2]})`;

        const someoneHere = occupied.has(`${r},${c}`);

        cells.push(
          <div
            key={`${r}-${c}`}
            className={`voxel-cell ${
              isPlayer ? "voxel-player" : "voxel-empty"
            }`}
            style={{
              backgroundColor: blank ? "transparent" : color,
              outline: someoneHere
                ? "1px solid rgba(255,255,255,0.6)"
                : "none",
            }}
          />
        );
      }
    }

    return cells;
  };

  // prepare players for ChatRoot:
  // ChatRoot expects each player = {id, row, col, username?, email?, chunk_id?}
  const enrichedPlayers = useMemo(() => {
    const chunkId =
      gameState?.chunk_id ??
      sessionStorage.getItem("current_chunk_id") ??
      null;
    return players.map((p) => ({
      ...p,
      username: p.id, // until you have real names in server, use the id
      email: "", // optional
      chunk_id: chunkId || "",
    }));
  }, [players, gameState]);

  const myId = authStorage.getUser()?.id ?? "";

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900 text-white overflow-x-hidden">
      {/* Header */}
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
          {/* connection status */}
          <div
            className={`flex items-center gap-2 px-4 py-2 rounded-full ${
              isConnected
                ? "bg-green-500/20 text-green-300"
                : "bg-red-500/20 text-red-300"
            }`}
          >
            {isConnected ? <Wifi size={18} /> : <WifiOff size={18} />}
            <span className="font-medium">
              {isConnected ? "Connected" : "Connecting..."}
            </span>
          </div>

          {/* player count */}
          <div className="flex items-center gap-2 px-4 py-2 rounded-full bg-blue-500/20 text-blue-300">
            <Users size={18} />
            <span className="font-medium">{playerCount} Players</span>
          </div>

          {/* last action */}
          {lastAction && (
            <div className="flex items-center gap-2 px-4 py-2 rounded-full bg-purple-500/20 text-purple-300 animate-pulse">
              <Gamepad2 size={18} />
              <span className="font-medium">{lastAction}</span>
            </div>
          )}
        </div>
      </div>

      {/* Grid + Chat side by side */}
      <div className="flex flex-row-reverse min-h-[60vh]">
        {/* world grid panel */}
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

        {/* chat panel */}
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
                gameState?.chunk_id ??
                sessionStorage.getItem("current_chunk_id") ??
                null
              }
              playersInChunk={enrichedPlayers}
            />
          )}
        </div>
      </div>

      {/* Floating chat toggle */}
      <button
        onClick={() => setShowChat((prev) => !prev)}
        className="fixed top-6 right-6 bg-cyan-600 hover:bg-cyan-500 text-white p-3 rounded-full shadow-xl transition-all z-[10000]"
        title={showChat ? "Close Chat" : "Open Chat"}
      >
        {showChat ? <X size={22} /> : <MessageCircle size={22} />}
      </button>

      {/* connection + players footer bubble */}
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

      {/* world announcement */}
      {notice && (
        <div className="fixed top-4 left-1/2 -translate-x-1/2 bg-blue-50/90 text-blue-800 px-4 py-2 rounded-lg shadow-lg border border-blue-200">
          {notice}
        </div>
      )}

      {/* world scroll composer (key 'm') */}
      {showMessageInput && (
        <MessageInput
          onSubmit={(content: string) => {
            // For world scrolls (command "m"), we still send as game command
            // not chat DM.
            sendCommand(JSON.stringify({ command: "m", content }));
            setShowMessageInput(false);
          }}
          onClose={() => setShowMessageInput(false)}
        />
      )}

      {/* error HUD and ephemeral message bubble */}
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

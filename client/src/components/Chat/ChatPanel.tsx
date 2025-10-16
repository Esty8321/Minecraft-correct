// import { useEffect, useState } from "react";
// import { authStorage } from "../../utils/auth";

// export default function ChatPanel() {
//   const [messages, setMessages] = useState<any[]>([]);
//   const [message, setMessage] = useState("");
//   const [ws, setWs] = useState<WebSocket | null>(null);
//   const [targetId, setTargetId] = useState<string>("");

//   useEffect(() => {
//     const user = authStorage.getUser();
//     const token = authStorage.getToken();
//     if (!user || !token) return;

//     const socket = new WebSocket(`ws://localhost:8080/chat/ws?token=${encodeURIComponent(token)}`);
//     socket.onopen = () => {
//       socket.send(JSON.stringify({ player_id: user.id }));
//     };
//     socket.onmessage = (e) => {
//       const msg = JSON.parse(e.data);
//       setMessages((prev) => [...prev, msg]);
//     };

//     socket.onclose = () => {
//       console.log("[CHAT] Disconnected");
//     }
//     setWs(socket);
//     return () => socket.close();
//   }, []);

//   const sendMessage = () => {
//     if (!ws || !message.trim()) return;
//     const user = authStorage.getUser();
//     if (!user) return;
//     let target = targetId
//     if (!target) {
//       const storedTarget = sessionStorage.getItem("chat_target_id")
//       if (storedTarget) {
//         console.log("Choose destingation for sent");
//         return;
//       }
//     }

//     ws.send(JSON.stringify({
//       from: user?.id,
//       to: target, // example target, could be selected later
//       message,
//       timestamp: new Date().toISOString(),
//     }));
//     setMessage("");
//   };

//   return (
//     <div className="flex flex-col w-1/2 h-screen border-r border-gray-200 bg-gray-50">
//       <div className="flex-1 overflow-y-auto p-4">
//         {messages.map((m, i) => (
//           <div key={i} className="mb-2">
//             <strong>{m.from}</strong>: {m.message}
//           </div>
//         ))}
//       </div>
//       <div className="p-4 flex border-t">
//         <input
//           className="flex-1 border rounded px-3 py-2 mr-2"
//           value={message}
//           onChange={(e) => setMessage(e.target.value)}
//           placeholder="Type message..."
//         />
//         <button onClick={sendMessage} className="bg-blue-500 text-white px-4 rounded">
//           Send
//         </button>
//       </div>
//     </div>
//   );
// }


import React, { useEffect, useRef, useState } from "react";
import { Send } from "lucide-react";
import { authStorage } from "../../utils/auth";

interface ChatMessage {
  from: string;
  to: string;
  message: string;
  timestamp: string;
}

const ChatPanel: React.FC = () => {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [message, setMessage] = useState("");
  const [isConnected, setIsConnected] = useState(false);

  const wsRef = useRef<WebSocket | null>(null);
  const queueRef = useRef<string[]>([]); // ← queue of unsent messages

  // ------------------ connect WebSocket ------------------
  useEffect(() => {
    const user = authStorage.getUser();
    const token = authStorage.getToken();
    if (!user || !token) return;

    const ws = new WebSocket(
      `ws://localhost:8080/chat/ws?token=${encodeURIComponent(token)}`
    );
    wsRef.current = ws;

    ws.onopen = () => {
      console.log("[CHAT] Connected ✅");
      setIsConnected(true);
      // send player_id (required by chat server)
      ws.send(JSON.stringify({ player_id: user.id }));

      // flush any queued messages
      if (queueRef.current.length > 0) {
        console.log(`[CHAT] Flushing ${queueRef.current.length} queued messages`);
        queueRef.current.forEach((msg) => ws.send(msg));
        queueRef.current = [];
      }
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === "message") {
          setMessages((prev) => [...prev, data]);
        }
      } catch (err) {
        console.warn("[CHAT] Parse error", err);
      }
    };

    ws.onclose = () => {
      console.log("[CHAT] Disconnected ❌");
      setIsConnected(false);
      wsRef.current = null;

      // Optional: try auto-reconnect after short delay
      setTimeout(() => {
        console.log("[CHAT] Reconnecting...");
        window.location.reload();
      }, 3000);
    };

    return () => {
      ws.close();
    };
  }, []);

  // ------------------ sendMessage with queue ------------------
  const sendMessage = () => {
    const user = authStorage.getUser();
    if (!user) return;

    const ws = wsRef.current;
    const targetId = sessionStorage.getItem("chat_target_id");
    if (!targetId) {
      console.log("⚠️ No target selected");
      return;
    }

    const payload = JSON.stringify({
      type: "message",
      from: user.id,
      to: targetId,
      message,
      timestamp: new Date().toISOString(),
    });

    if (!ws) {
      console.warn("[CHAT] No WebSocket available — queueing message");
      queueRef.current.push(payload);
      return;
    }

    switch (ws.readyState) {
      case WebSocket.OPEN:
        ws.send(payload);
        break;

      case WebSocket.CONNECTING:
        console.log("[CHAT] WS connecting — queueing message");
        queueRef.current.push(payload);
        break;

      case WebSocket.CLOSING:
      case WebSocket.CLOSED:
      default:
        console.log("[CHAT] WS closed — queueing message");
        queueRef.current.push(payload);
        break;
    }

    // optimistic UI update
    setMessages((prev) => [
      ...prev,
      { from: user.id, to: targetId, message, timestamp: new Date().toISOString() },
    ]);
    setMessage("");
  };

  // ------------------ UI ------------------
  return (
    <div className="flex flex-col h-full bg-slate-900 text-white p-4">
      <div className="flex-1 overflow-y-auto space-y-2">
        {messages.map((m, i) => (
          <div
            key={i}
            className={`p-2 rounded-lg ${
              m.from === authStorage.getUser()?.id
                ? "bg-blue-600 self-end text-right"
                : "bg-slate-700 self-start text-left"
            }`}
          >
            <div className="text-sm opacity-80">
              {m.from === authStorage.getUser()?.id ? "You" : m.from}
            </div>
            <div>{m.message}</div>
          </div>
        ))}
      </div>

      <div className="flex items-center mt-3 gap-2">
        <input
          type="text"
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && sendMessage()}
          placeholder={
            isConnected
              ? "Type a message..."
              : "Connecting... messages will queue"
          }
          className="flex-1 rounded-lg p-2 text-black"
        />
        <button
          onClick={sendMessage}
          disabled={!message.trim()}
          className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg flex items-center gap-2"
        >
          <Send size={16} />
          Send
        </button>
      </div>
    </div>
  );
};

export default ChatPanel;

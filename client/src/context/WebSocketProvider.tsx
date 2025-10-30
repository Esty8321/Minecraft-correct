import React, { createContext, useContext } from "react";
import { useWebSocket } from "../hooks/useWebSocket";

// Create context for the WebSocket hook
const WebSocketContext = createContext<ReturnType<typeof useWebSocket> | null>(null);

export const WebSocketProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const ws = useWebSocket(); // ✅ only one connection created here
  return <WebSocketContext.Provider value={ws}>{children}</WebSocketContext.Provider>;
};

// Hook to access the shared WebSocket
export const useSharedWebSocket = () => {
  const ctx = useContext(WebSocketContext);
  if (!ctx) throw new Error("useSharedWebSocket must be used inside <WebSocketProvider>");
  return ctx;
};

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type {
  Message as ChatMessage,
  Player,
  WebSocketMessage,
  Reaction,
} from "../types";
import { authStorage } from "../utils/auth";

/**
 * Decide backend host:
 * - in dev: ws://127.0.0.1:8080/ws
 * - in prod: ws(s)://<actual-host>/ws
 */
function backendHost(): string {
  const h = window.location.hostname;
  return h === "localhost" || h === "127.0.0.1" ? "127.0.0.1" : h;
}

function wsUrl(): string {
  const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
  // IMPORTANT: match your FastAPI websocket route
  // In server main.py we had: @app.websocket("/ws")
  // If you're actually mounting FastAPI under /game, adjust here.

  return `${proto}//${backendHost()}:8080/game/ws`;
}

type UseWS = {
  isConnected: boolean;
  messages: ChatMessage[];
  selectedPlayer: Player | null;
  selectPlayer: (p: Player) => void;
  sendMessage: (
    text: string,
    quotedMessage?: ChatMessage,
    extras?: { chunkId?: string | null }
  ) => void;
  reactToMessage: (id: string, reaction: Reaction) => void;
  deleteMessage: (messageId: string) => void;
  activePlayers: Player[];
  currentPlayerId?: string;
  unreadCounts: Record<string, number>;
  markRead: (playerId: string) => void;
  sendCommand: (command: string) => void; // game commands ("up","down", etc.)
};

export function useWebSocket(): UseWS {
  const socketRef = useRef<WebSocket | null>(null);

  const [isConnected, setIsConnected] = useState(false);

  // chat messages currently displayed in UI
  const [messages, setMessages] = useState<ChatMessage[]>([]);

  // sidebar list of players (we’re actually getting that live from VoxelGrid,
  // so we don’t populate this here, but we keep state around for future if needed)
  const [activePlayers] = useState<Player[]>([]);

  // who we’re currently chatting with
  const [selectedPlayer, _setSelectedPlayer] = useState<Player | null>(null);

  // who am I
  const [currentPlayerId, _setCurrentPlayerId] = useState<string>();

  // unread counts per playerId
  const [unreadCounts, setUnreadCounts] = useState<Record<string, number>>({});

  // refs (so event handlers can read latest without stale closure)
  const selectedPlayerRef = useRef<Player | null>(null);
  const currentPlayerIdRef = useRef<string | undefined>(undefined);

  // track which messages we've already inserted
  const seenIdsRef = useRef<Set<string>>(new Set());
  // quick lookup by id to attach quoted message bodies
  const messageIndexRef = useRef<Map<string, ChatMessage>>(new Map());

  const setSelectedPlayer = useCallback((p: Player | null) => {
    selectedPlayerRef.current = p;
    _setSelectedPlayer(p);
  }, []);

  const setCurrentPlayerId = useCallback((id?: string) => {
    currentPlayerIdRef.current = id;
    _setCurrentPlayerId(id);
  }, []);

  // attach quoted_message inline for UI
  const attachQuoteIfAny = useCallback((raw: any): ChatMessage => {
    const quotedId = raw?.quotedId || raw?.quoted_id;
    if (quotedId) {
      const q = messageIndexRef.current.get(quotedId);
      if (q) {
        return { ...(raw as ChatMessage), quoted_message: q } as any;
      }
    }
    return raw as ChatMessage;
  }, []);

  // merge new messages into state (idempotent)
  const upsertMessages = useCallback(
    (list: ChatMessage[]) => {
      const withQuotes = list.map(attachQuoteIfAny);

      setMessages((prev) => {
        const next = [...prev];
        for (const m of withQuotes) {
          if (!seenIdsRef.current.has(m.id)) {
            next.push(m);
            seenIdsRef.current.add(m.id);
          } else {
            const i = next.findIndex((x) => x.id === m.id);
            if (i >= 0) {
              next[i] = { ...next[i], ...m };
            }
          }
        }
        return next;
      });

      // also update index
      for (const m of withQuotes) {
        messageIndexRef.current.set(m.id, m);
      }
    },
    [attachQuoteIfAny]
  );

  // establish single websocket connection on mount
  useEffect(() => {
    const url = wsUrl();
    const token = authStorage.getToken();
    const ws = new WebSocket(`${url}?token=${encodeURIComponent(token ?? "")}`);
    socketRef.current = ws;
    console.log("[WS] connecting to", url);

    ws.onopen = () => {
      setIsConnected(true);
      console.log("[WS] open");

      const user = authStorage.getUser();
      if (user?.id) {
        // announce my identity to server session_store
        ws.send(JSON.stringify({ player_id: user.id }));
        setCurrentPlayerId(user.id);
      }
    };

    ws.onmessage = (ev) => {
      const data: WebSocketMessage | any = JSON.parse(ev.data);

       if (data && ["matrix", "announcement", "error"].includes(data.type)) {
          window.dispatchEvent(new CustomEvent("game-update", { detail: data }));
          return;
        }
      //
      // CHAT MESSAGES
      //

      // server sends full history for a pair after "select"
      if (data.type === "history") {
        const msgs: ChatMessage[] = (data.messages ?? []).map((m: any) => {
          const ts = m.timestamp ?? new Date().toISOString();
          const id = m.id ?? `${ts}|${m.from}|${m.message ?? ""}`;
          return attachQuoteIfAny({
            id,
            from: m.from,
            to: m.to ?? "",
            message: m.message ?? "",
            timestamp: ts,
            type: m.type === "bot" ? "bot" : "user",
          });
        });

        // reset seenIds to match fresh history:
        seenIdsRef.current = new Set(msgs.map((m) => m.id));
        setMessages(msgs);
        for (const m of msgs) {
          messageIndexRef.current.set(m.id, m);
        }

        return;
      }

      // server broadcast for a new single message (live DM)
      if (data.type === "message") {
        const ts: string = data.timestamp ?? new Date().toISOString();
        const sender: string = data.sender ?? "unknown";
        const id = data.id ?? `${ts}|${sender}|${data.message ?? ""}`;

        if (seenIdsRef.current.has(id)) return;

        // figure who is "to" for local struct
        const me = currentPlayerIdRef.current ?? "";
        const sel = selectedPlayerRef.current?.id ?? "";

        const toComputed = (data as any).to ?? (sender === me ? sel : me);

        const msg = attachQuoteIfAny({
          id,
          from: sender,
          to: toComputed,
          message: data.message ?? "",
          timestamp: ts,
          type: (data as any).isBot ? "bot" : "user",
        });

        upsertMessages([msg]);

        // unread counter:
        // if it's addressed to me AND I'm NOT currently viewing that sender's chat tab ⇒ mark unread
        if (
          toComputed === me &&
          (!selectedPlayerRef.current ||
            selectedPlayerRef.current.id !== sender)
        ) {
          setUnreadCounts((prev) => ({
            ...prev,
            [sender]: (prev[sender] || 0) + 1,
          }));
        }

        return;
      }

      // reaction updates (like / dislike)
      if (data.type === "react") {
        const { messageId, my_reaction } = data;
        setMessages((prev) =>
          prev.map((m) =>
            m.id === messageId ? { ...m, my_reaction } : m
          )
        );
        const cur = messageIndexRef.current.get(messageId);
        if (cur) {
          messageIndexRef.current.set(messageId, {
            ...cur,
            my_reaction,
          });
        }
        return;
      }

      // unread counts sync
      if (data.type === "unread") {
        const me = currentPlayerIdRef.current;
        if (me && (data as any).to === me) {
          setUnreadCounts((prev) => ({
            ...prev,
            [(data as any).from]: (data as any).count,
          }));
        }
        return;
      }
    };

    ws.onclose = () => {
      setIsConnected(false);
      socketRef.current = null;
    };

    return () => {
      try {
        ws.close();
      } catch {
        /* ignore */
      }
    };
  }, [attachQuoteIfAny, upsertMessages, setCurrentPlayerId]);

 

  // const sendCommand = useCallback(
  //   (command: string | { command: string; [k: string]: any }) => {
  //     const ws = socketRef.current;
  //     if (!ws || ws.readyState !== WebSocket.OPEN) return;

  //     const payload =
  //       typeof command === "string" ? { command } : command;

  //     ws.send(JSON.stringify(payload)); // ✅ שולחים את ה-payload הנכון
  //   },
  //   []
  // );

  const sendCommand = useCallback(
  (command: string | { command: string; [key: string]: any }) => {
    const ws = socketRef.current;
    if (!ws || ws.readyState !== WebSocket.OPEN) return;

    // ✅ עכשיו אם שולחים אובייקט הוא לא נארז שוב
    const payload = typeof command === "string" ? { command } : command;
    ws.send(JSON.stringify(payload));
  },
  []
);

  // select which player I'm chatting with -> tells server "select"
  const selectPlayer = useCallback(
    (p: Player) => {
      setSelectedPlayer(p);

      const ws = socketRef.current;
      if (!ws || ws.readyState !== WebSocket.OPEN) return;

      ws.send(JSON.stringify({ type: "select", selectedPlayer: p.id }));
      ws.send(JSON.stringify({ type: "read", with: p.id }));

      // locally clear unread for that user
      setUnreadCounts((prev) => ({ ...prev, [p.id]: 0 }));
    },
    [setSelectedPlayer]
  );

  // manual markRead if user clicks in Sidebar
  const markRead = useCallback((playerId: string) => {
    const ws = socketRef.current;
    if (!ws || ws.readyState !== WebSocket.OPEN) return;

    ws.send(JSON.stringify({ type: "read", with: playerId }));
    setUnreadCounts((prev) => ({ ...prev, [playerId]: 0 }));
  }, []);

  // send chat message "DM"
  const sendMessage = useCallback(
    (
      text: string,
      quotedMessage?: ChatMessage,
      extras?: { chunkId?: string | null }
    ) => {
      const ws = socketRef.current;
      const sel = selectedPlayerRef.current;
      const me = currentPlayerIdRef.current;

      if (!ws || ws.readyState !== WebSocket.OPEN) return;
      if (!sel || !me || !text.trim()) return;

      const ts = new Date().toISOString();
      const id = `${ts}|${me}|${text}`;

      const payload: any = {
        type: "message",
        message: text,
        selectedPlayer: sel.id,
        timestamp: ts,
      };

      if (quotedMessage) {
        payload.quotedId = quotedMessage.id;
      }
      if (extras?.chunkId) {
        payload.chunkId = extras.chunkId;
      }

      // send to server over same socket
      ws.send(JSON.stringify(payload));

      // optimistic UI insert
      const optimistic: ChatMessage = {
        id,
        from: me,
        to: sel.id,
        message: text,
        timestamp: ts,
        type: "user",
        ...(quotedMessage ? { quoted_message: quotedMessage } : {}),
      } as any;

      seenIdsRef.current.add(id);
      messageIndexRef.current.set(id, optimistic);

      setMessages((prev) => [...prev, optimistic]);
    },
    []
  );

  // react to a message
  const reactToMessage = useCallback(
    (messageId: string, reaction: Reaction) => {
      const ws = socketRef.current;
      if (!ws || ws.readyState !== WebSocket.OPEN) return;
      ws.send(JSON.stringify({ type: "react", messageId, reaction }));
    },
    []
  );

  // soft delete a message (client optimism)
  const deleteMessage = useCallback((messageId: string) => {
    const ws = socketRef.current;
    if (!ws || ws.readyState !== WebSocket.OPEN) return;

    ws.send(JSON.stringify({ type: "delete", messageId }));
    setMessages((prev) =>
      prev.map((m) =>
        m.id === messageId ? { ...m, deleted: true, message: "" } : m
      )
    );
  }, []);

  //
  // expose hook API
  //
  return useMemo(
    () => ({
      isConnected,
      messages,
      selectedPlayer,
      selectPlayer,
      sendMessage,
      reactToMessage,
      deleteMessage,
      activePlayers, // currently unused because VoxelGrid holds it
      currentPlayerId,
      unreadCounts,
      markRead,
      sendCommand,
    }),
    [
      isConnected,
      messages,
      selectedPlayer,
      selectPlayer,
      sendMessage,
      reactToMessage,
      deleteMessage,
      activePlayers,
      currentPlayerId,
      unreadCounts,
      markRead,
      sendCommand,
    ]
  );
}
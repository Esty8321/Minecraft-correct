import React, {
  useState,
  useRef,
  useEffect,
  useMemo,
  useCallback,
} from "react";
import { Send, Smile, Settings, X, Quote, Users } from "lucide-react";
import MessageItem from "./MessageItem";
import EmojiPicker from "./EmojiPicker";
import { Message, Player } from "../../types";

type Reaction = "up" | "down" | null;

interface ChatInterfaceProps {
  messages: Message[];
  selectedPlayer: Player | null;
  currentPlayerId: string;
  onSendMessage: (message: string, quotedMessage?: Message) => void;
  onReactMessage: (messageId: string, reaction: Reaction) => void;
  onDeleteMessage: (messageId: string) => void;

  // live players in the chunk
  playersInChunk?: {
    id: string;
    username?: string;
    row: number;
    col: number;
    chunk_id?: string;
  }[];
  nearestPlayerId?: string;
}

const ChatInterface: React.FC<ChatInterfaceProps> = ({
  messages,
  selectedPlayer,
  currentPlayerId,
  onSendMessage,
  onReactMessage,
  onDeleteMessage,
  playersInChunk = [],
  nearestPlayerId,
}) => {
  const [input, setInput] = useState("");
  const [quotedMessage, setQuotedMessage] = useState<Message | undefined>(
    undefined
  );
  const [showEmojiPicker, setShowEmojiPicker] = useState(false);
  const [showPlayers, setShowPlayers] = useState(false);
  const endRef = useRef<HTMLDivElement | null>(null);

  // safe display text even if deleted
  const msgText = (m?: Message) =>
    !m ? "" : (m as any).deleted ? "Message deleted" : m.message ?? "";

  // whether I’m allowed to send to selectedPlayer
  const canSend = useMemo(() => {
    if (!selectedPlayer) return false;
    if (selectedPlayer.id === currentPlayerId) return false; // can't message self
    if (!nearestPlayerId) return true;
    return selectedPlayer.id === nearestPlayerId;
  }, [selectedPlayer, nearestPlayerId, currentPlayerId]);

  // auto-scroll on new messages
  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleSend = useCallback(() => {
    const text = input.trim();
    if (!text) return;

    // re-check guard before actually firing
    if (!selectedPlayer) return;
    if (selectedPlayer.id === currentPlayerId) {
      alert("You can't chat with yourself.");
      return;
    }
    if (nearestPlayerId && selectedPlayer.id !== nearestPlayerId) {
      alert("You can only chat with the nearest player in your chunk.");
      return;
    }

    onSendMessage(text, quotedMessage);
    setInput("");
    setQuotedMessage(undefined);
  }, [
    input,
    quotedMessage,
    onSendMessage,
    selectedPlayer,
    currentPlayerId,
    nearestPlayerId,
  ]);

  const handleEmojiSelect = (emoji: string) => setInput((v) => v + emoji);
  const handleGifSelect = (gifUrl: string) => setInput((v) => v + ` ${gifUrl} `);

  return (
    <div className="flex flex-col h-full">
      {/* Toolbar */}
      <div className="px-4 py-2 border-b border-slate-700 flex items-center justify-between">
        <div className="text-sm">
          {selectedPlayer ? (
            <>
              Chat with{" "}
              <span className="font-semibold">
                {selectedPlayer.username}
              </span>
              {selectedPlayer.id === currentPlayerId && (
                <span className="ml-1 text-xs px-1 py-0.5 rounded bg-emerald-600/40 border border-emerald-500/60">
                  you
                </span>
              )}
              {nearestPlayerId &&
                selectedPlayer.id === nearestPlayerId &&
                selectedPlayer.id !== currentPlayerId && (
                  <span className="ml-1 text-xs px-1 py-0.5 rounded bg-sky-600/40 border border-sky-500/60">
                    nearest
                  </span>
                )}
            </>
          ) : (
            <span className="text-slate-400">Select a player to start</span>
          )}
        </div>

        <div className="flex items-center gap-2">
          {/* player list modal */}
          <button
            onClick={() => setShowPlayers((v) => !v)}
            title="Players in chunk"
            className="p-2 rounded hover:bg-slate-600/50"
          >
            <Users size={18} />
          </button>

          <button
            className="p-2 rounded hover:bg-slate-600/50"
            title="Settings"
          >
            <Settings size={18} />
          </button>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-auto p-4 space-y-2">
        {messages.map((m, idx) => {
          const prevMessage = idx > 0 ? messages[idx - 1] : null;
          const nextMessage = idx < messages.length - 1 ? messages[idx + 1] : null;
          const isOwn = m.from === currentPlayerId;

          return (
            <MessageItem
              key={m.id}
              message={m}
              prevMessage={prevMessage}
              nextMessage={nextMessage}
              isOwn={isOwn}
              currentPlayerId={currentPlayerId}
              onReact={(messageId, reaction) =>
                onReactMessage(messageId, reaction)
              }
              onDelete={(id) => onDeleteMessage(id)}
              onQuote={() => setQuotedMessage(m)}
            />
          );
        })}
        <div ref={endRef} />
      </div>

      {/* Quoted preview */}
      {quotedMessage && (
        <div className="px-4 py-2 border-t border-slate-700 bg-slate-800/60 text-xs flex items-center gap-2">
          <Quote size={14} />
          <div className="flex-1 truncate">
            Replying to{" "}
            <span className="font-semibold">{quotedMessage.from}</span>:{" "}
            {msgText(quotedMessage)}
          </div>
          <button
            className="p-1 rounded hover:bg-slate-700"
            onClick={() => setQuotedMessage(undefined)}
          >
            <X size={16} />
          </button>
        </div>
      )}

      {/* Input bar */}
      <div className="p-3 border-t border-slate-700 flex items-center gap-2">
        <button
          className="p-2 rounded hover:bg-slate-700"
          title="Emoji / GIF"
          onClick={() => setShowEmojiPicker((v) => !v)}
        >
          <Smile size={18} />
        </button>

        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              if (canSend) handleSend();
            }
          }}
          className="flex-1 bg-slate-800 border border-slate-700 rounded px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-sky-500"
          placeholder={
            selectedPlayer
              ? canSend
                ? `Message ${selectedPlayer.username}...`
                : `You can only chat with the nearest player`
              : "Select a player..."
          }
        />

        <button
          onClick={handleSend}
          disabled={!input.trim() || !canSend}
          className={`px-3 py-2 rounded flex items-center gap-2 transition ${
            !input.trim() || !canSend
              ? "bg-slate-700 text-slate-400 cursor-not-allowed"
              : "bg-blue-600 hover:bg-blue-700 text-white"
          }`}
        >
          <Send size={16} />
          Send
        </button>
      </div>

      {/* Emoji/GIF */}
      {showEmojiPicker && (
        <EmojiPicker
          onEmojiSelect={handleEmojiSelect}
          onGifSelect={handleGifSelect}
          onClose={() => setShowEmojiPicker(false)}
        />
      )}

      {/* Players modal */}
      {showPlayers && (
        <div className="absolute inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-slate-800 border border-slate-600 rounded-xl p-4 w-80 max-h-[70vh] overflow-auto shadow-2xl">
            <div className="flex items-center justify-between mb-2">
              <div className="font-semibold">Players in this chunk</div>
              <button
                className="p-1 rounded hover:bg-slate-700"
                onClick={() => setShowPlayers(false)}
              >
                <X size={16} />
              </button>
            </div>
            <ul className="space-y-2">
              {playersInChunk.map((p) => {
                const isMe = p.id === currentPlayerId;
                const isNearest = p.id === (nearestPlayerId || "");
                return (
                  <li
                    key={p.id}
                    className={`flex items-center justify-between p-2 rounded border ${
                      isNearest
                        ? "border-emerald-500 animate-pulse"
                        : "border-slate-600"
                    } ${!isMe && !isNearest ? "opacity-60" : ""}`}
                  >
                    <span>
                      {p.username ?? p.id}{" "}
                      {isMe && (
                        <span className="ml-1 text-xs px-1 py-0.5 rounded bg-emerald-600/40 border border-emerald-500/60">
                          you
                        </span>
                      )}
                    </span>
                    <span className="text-xs text-slate-400">
                      ({p.row},{p.col})
                    </span>
                  </li>
                );
              })}
            </ul>
          </div>
        </div>
      )}
    </div>
  );
};

export default ChatInterface;


import React, { useState, useRef, useEffect, useMemo, useCallback } from 'react';
import { Send, Smile, Settings, X, Quote } from 'lucide-react';
import MessageItem from './MessageItem';
import EmojiPicker from './EmojiPicker';
import { Message, Player} from '../../types';

type Reaction = 'up' | 'down' | null;

interface ChatInterfaceProps {
  messages: Message[];
  selectedPlayer: Player | null;
  currentPlayerId: string;
  onSendMessage: (message: string, quotedMessage?: Message) => void;
  onReactMessage: (messageId: string, reaction: Reaction) => void;
  /** NEW: מחיקה רכה של הודעה (לקוח->שרת דרך ה-hook) */
  onDeleteMessage: (messageId: string) => void;
  showEmojiPicker: boolean;
  setShowEmojiPicker: (show: boolean) => void;
  onCustomizationToggle: () => void;
  onMarkRead: (playerId: string) => void;
}

const SCROLL_STICKY_THRESHOLD = 28;

function ModernToggle({
  checked,
  onChange,
  label,
}: {
  checked: boolean;
  onChange: (v: boolean) => void;
  label?: React.ReactNode;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      onClick={() => onChange(!checked)}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          onChange(!checked);
        }
      }}
      className="group inline-flex items-center gap-3 select-none"
      title="Toggle emoji send behavior"
    >
      {label && <span className="text-xs md:text-sm text-slate-200">{label}</span>}
      <span
        className={`relative inline-flex h-6 w-11 items-center rounded-full border transition
          ${checked ? 'bg-cyan-500/90 border-cyan-400 shadow-[0_0_0_2px_rgba(0,255,255,0.15)]'
                    : 'bg-slate-700/80 border-slate-600'}`}
      >
        <span
          className={`ml-[2px] inline-block h-5 w-5 transform rounded-full bg-white
                      shadow-md transition-transform duration-300
                      ${checked ? 'translate-x-5' : 'translate-x-0'}`}
        />
      </span>
    </button>
  );
}

const ChatInterface: React.FC<ChatInterfaceProps> = ({
  messages,
  selectedPlayer,
  currentPlayerId,
  onSendMessage,
  onReactMessage,
  onDeleteMessage, // NEW
  showEmojiPicker,
  setShowEmojiPicker,
  onCustomizationToggle,
  onMarkRead,
}) => {
  const [messageText, setMessageText] = useState('');
  const [quotedMessage, setQuotedMessage] = useState<Message | null>(null);
  const [isTyping, setIsTyping] = useState(false);
  const [isAtBottom, setIsAtBottom] = useState(true);
  const [highlightedId, setHighlightedId] = useState<string | null>(null);

  const [sendEmojiImmediately, setSendEmojiImmediately] = useState<boolean>(() => {
    const v = localStorage.getItem('chat_sendEmojiImmediately');
    return v ? v === '1' : false;
  });
  useEffect(() => {
    localStorage.setItem('chat_sendEmojiImmediately', sendEmojiImmediately ? '1' : '0');
  }, [sendEmojiImmediately]);

  const [showEmojiMenu, setShowEmojiMenu] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const onDown = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setShowEmojiMenu(false);
      }
    };
    if (showEmojiMenu) document.addEventListener('mousedown', onDown);
    return () => document.removeEventListener('mousedown', onDown);
  }, [showEmojiMenu]);

  const listRef = useRef<HTMLDivElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const typingTimeoutRef = useRef<NodeJS.Timeout>();
  const messageRefs = useRef<Record<string, HTMLDivElement | null>>({});
  const prevThreadIdRef = useRef<string | null>(null);
  const prevLenRef = useRef<number>(0);

  // הודעות של השיחה הפעילה בלבד
  const filteredMessages = useMemo(() => {
    if (!selectedPlayer) return [];
    const partner = selectedPlayer.id;
    return messages
      .filter(
        (m) =>
          (m.from === currentPlayerId && m.to === partner) ||
          (m.from === partner && m.to === currentPlayerId) ||
          m.type === 'bot'
      )
      .sort((a, b) => (a.timestamp || '').localeCompare(b.timestamp || ''));
  }, [messages, selectedPlayer, currentPlayerId]);

  // מעבר בין שיחות
  useEffect(() => {
    const threadId = selectedPlayer?.id || null;
    if (prevThreadIdRef.current !== threadId) {
      messageRefs.current = {};
      setHighlightedId(null);
    }
    if (!threadId) {
      prevThreadIdRef.current = threadId;
      prevLenRef.current = filteredMessages.length;
      return;
    }
    onMarkRead(threadId);
    requestAnimationFrame(() => {
      messagesEndRef.current?.scrollIntoView({ behavior: 'auto' });
      setIsAtBottom(true);
      inputRef.current?.focus();
    });
    prevThreadIdRef.current = threadId;
    prevLenRef.current = filteredMessages.length;
  }, [selectedPlayer?.id, filteredMessages.length, onMarkRead]);

  // מעקב גלילה
  useEffect(() => {
    const el = listRef.current;
    if (!el) return;
    const onScroll = () => {
      const nearBottom = el.scrollHeight - (el.scrollTop + el.clientHeight) <= SCROLL_STICKY_THRESHOLD;
      setIsAtBottom(nearBottom);
    };
    el.addEventListener('scroll', onScroll, { passive: true });
    return () => el.removeEventListener('scroll', onScroll);
  }, []);

  // הדבקה לתחתית כשכבר בתחתית
  useEffect(() => {
    const grew = filteredMessages.length > prevLenRef.current;
    if (grew && isAtBottom) {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
    prevLenRef.current = filteredMessages.length;
  }, [filteredMessages.length, isAtBottom]);

  useEffect(() => {
    if (selectedPlayer) inputRef.current?.focus();
  }, [selectedPlayer]);

  const markReadAndStick = useCallback(() => {
    if (!selectedPlayer) return;
    onMarkRead(selectedPlayer.id);
    messagesEndRef.current?.scrollIntoView({ behavior: 'auto' });
    setIsAtBottom(true);
  }, [onMarkRead, selectedPlayer]);

  const handleMessagesAreaClick = useCallback(
    (e: React.MouseEvent<HTMLDivElement>) => {
      if (!selectedPlayer) return;
      const target = e.target as HTMLElement;
      const interactive = target.closest(
        'button, a, input, textarea, select, [role="button"], [contenteditable="true"], [data-no-stick]'
      );
      if (interactive) return;
      if (!isAtBottom) return;
      markReadAndStick();
    },
    [selectedPlayer, isAtBottom, markReadAndStick]
  );

  // שליחה
  const handleSendMessage = useCallback(() => {
    const text = messageText.trim();
    if (!text || !selectedPlayer) return;
    onSendMessage(text, quotedMessage || undefined);
    setMessageText('');
    setQuotedMessage(null);
    setIsTyping(false);
    markReadAndStick();
  }, [messageText, selectedPlayer, onSendMessage, quotedMessage, markReadAndStick]);

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  // הקלדה
  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setMessageText(e.target.value);
    if (!isTyping) setIsTyping(true);
    if (typingTimeoutRef.current) clearTimeout(typingTimeoutRef.current);
    typingTimeoutRef.current = setTimeout(() => setIsTyping(false), 1000);
    if (selectedPlayer && isAtBottom) markReadAndStick();
  };

  // אימוג'י / GIF
  const handleEmojiSelect = (emoji: string) => {
    if (!selectedPlayer) return;
    if (sendEmojiImmediately) {
      onSendMessage(emoji);
      setShowEmojiPicker(false);
      if (isAtBottom) markReadAndStick();
    } else {
      setMessageText((prev) => prev + emoji);
      inputRef.current?.focus();
      if (isAtBottom) markReadAndStick();
    }
  };

  const handleGifSelect = (gifUrl: string) => {
    if (!selectedPlayer) return;
    onSendMessage(gifUrl);
    setShowEmojiPicker(false);
    if (isAtBottom) markReadAndStick();
  };

  // בחירת הודעה לציטוט
  const handleQuoteMessage = (message: Message) => {
    setQuotedMessage(message);
    inputRef.current?.focus();
    if (selectedPlayer && isAtBottom) markReadAndStick();
  };

  // קפיצה להודעה המצוטטת + הדגשה סביב הבועה (נמחקת בלחיצה מחוץ לבועה בתוך MessageItem)
  const onScrollToQuotedMessage = useCallback((quotedMessageId: string) => {
    const el = messageRefs.current[quotedMessageId] || null;
    if (!el) return;
    el.scrollIntoView({ behavior: 'smooth', block: 'center' });
    setHighlightedId(quotedMessageId);
  }, []);

  return (
    <div className="flex-1 flex flex-col bg-gradient-to-br from-slate-950 to-slate-900 text-slate-100">
      {/* Header */}
      <div className="px-6 py-4 border-b border-slate-800/70 bg-slate-900/70 backdrop-blur-md">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            {selectedPlayer ? (
              <>
                <div className="w-10 h-10 rounded-2xl bg-gradient-to-br from-emerald-500 to-teal-500 flex items-center justify-center text-white font-bold shadow-lg shadow-emerald-900/30">
                  {selectedPlayer.username?.charAt(0).toUpperCase()}
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <h3 className="text-lg font-semibold tracking-tight">{selectedPlayer.username}</h3>
                    <span className="text-[11px] px-2 py-0.5 rounded-full bg-green-600/20 text-green-300 border border-green-500/30">
                      {selectedPlayer.status || 'online'}
                    </span>
                  </div>
                  <p className="text-[11px] text-slate-400">Level {selectedPlayer.level || 1}</p>
                </div>
              </>
            ) : (
              <div className="text-slate-400">Select a player to start chatting</div>
            )}
          </div>

          <button
            onClick={onCustomizationToggle}
            className="px-3 py-1.5 text-sm rounded-lg border border-slate-700 bg-slate-800/70 hover:bg-slate-700/70 transition-colors flex items-center gap-2"
          >
            <Settings className="w-4 h-4" />
            Customize
          </button>
        </div>
      </div>

      {/* Messages */}
      <div
        ref={listRef}
        onClick={handleMessagesAreaClick}
        className="flex-1 overflow-y-auto p-3 md:p-4 space-y-px bg-gradient-to-b from-slate-950 to-slate-900/70"
      >
        {selectedPlayer ? (
          <>
            {filteredMessages.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-full text-slate-400">
                <div className="text-6xl mb-4">💬</div>
                <p className="text-lg mb-2">Start the conversation!</p>
                <p className="text-sm">Send your first message to {selectedPlayer.username}</p>
              </div>
            ) : (
              filteredMessages.map((message, idx) => (
                <div
                  key={message.id}
                  ref={(el) => {
                    messageRefs.current[message.id] = el;
                  }}
                >
                  <MessageItem
                    message={message}
                    prevMessage={idx > 0 ? filteredMessages[idx - 1] : null}
                    nextMessage={idx < filteredMessages.length - 1 ? filteredMessages[idx + 1] : null}
                    isOwn={message.from === currentPlayerId}
                    onReact={onReactMessage}
                    onQuote={handleQuoteMessage}
                    currentPlayerId={currentPlayerId}
                    onJumpTo={onScrollToQuotedMessage}
                    isHighlighted={highlightedId === message.id}
                    onClearHighlight={() => setHighlightedId(null)}
                    /** NEW: העברת מחיקה רכה לתוך MessageItem */
                    onDelete={(id) => onDeleteMessage(id)}
                  />
                </div>
              ))
            )}
            <div ref={messagesEndRef} />
          </>
        ) : (
          <div className="flex flex-col items-center justify-center h-full text-slate-400">
            <div className="text-6ל mb-4">🎮</div>
            <p className="text-lg mb-2">Welcome to Game Chat!</p>
            <p className="text-sm">Select a player from the sidebar to start chatting</p>
          </div>
        )}
      </div>

      {/* Quoted bar */}
      {quotedMessage && (
        <div className="px-4 py-2 bg-slate-800/70 border-t border-slate-800/60">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Quote className="w-4 h-4 text-slate-400" />
              <span className="text-sm text-slate-300">
                Replying to <span className="font-semibold">{quotedMessage.from}</span>:{" "}
                {/* NEW: אם המצוטט נמחק – מציגים placeholder */}
                {(quotedMessage as any).deleted ? 'Message deleted' : quotedMessage.message.slice(0, 50)}...
              </span>
            </div>
            <button onClick={() => setQuotedMessage(null)} className="p-1 text-slate-400 hover:text-white">
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}

      {/* Composer */}
      <div className="px-4 md:px-6 py-4 border-t border-slate-800/70 bg-slate-900/70 backdrop-blur-md relative">
        <div className="flex items-end gap-3">
          {/* Emoji */}
          <div className="relative">
            <button
              type="button"
              onClick={() => setShowEmojiPicker(!showEmojiPicker)}
              className={`relative p-3 rounded-xl transition-all duration-200 hover:scale-105 border
                ${showEmojiPicker
                  ? 'bg-cyan-600 text-white border-cyan-500'
                  : sendEmojiImmediately
                    ? 'bg-slate-800 text-cyan-300 border-cyan-500/40 hover:bg-slate-700'
                    : 'bg-slate-800 text-slate-300 border-slate-700 hover:text-white hover:bg-slate-700'
                }`}
              title="Emojis"
            >
              <Smile className="w-5 h-5" />
              <span
                onClick={(e) => { e.stopPropagation(); setShowEmojiMenu((v) => !v); }}
                className={`absolute -top-1 -right-1 rounded-full px-1.5 py-[2px] text-[10px] font-semibold
                  border ${showEmojiMenu ? 'bg-slate-900 border-cyan-400 text-cyan-300' : 'bg-slate-900 border-slate-600 text-slate-300'}`}
                title="More options"
                aria-label="More emoji options"
              >
                ⋯
              </span>
            </button>

            {showEmojiMenu && (
              <div
                ref={menuRef}
                className="absolute left-0 bottom-full mb-2 w-64 rounded-xl border border-slate-700 bg-slate-900 shadow-2xl z-50 p-3"
                onMouseDown={(e) => e.stopPropagation()}
              >
                <div className="text-slate-300 text-sm mb-2">Emoji options</div>

                <div className="flex items-center justify-between py-2">
                  <span className="text-slate-200 text-sm">Send emoji instantly</span>
                  <ModernToggle
                    checked={sendEmojiImmediately}
                    onChange={(v) => setSendEmojiImmediately(v)}
                  />
                </div>

                <button
                  className="mt-2 ו-full text-left text-sm px-3 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 transition"
                  onClick={() => { setShowEmojiPicker(true); setShowEmojiMenu(false); }}
                >
                  Open Emoji Picker
                </button>
              </div>
            )}
          </div>

          {/* Input */}
          <div className="flex-1">
            <input
              ref={inputRef}
              type="text"
              value={messageText}
              onChange={handleInputChange}
              onKeyPress={handleKeyPress}
              placeholder={selectedPlayer ? `Message ${selectedPlayer.username}...` : 'Select a player to chat...'}
              disabled={!selectedPlayer}
              className="w-full px-4 py-3 rounded-xl bg-slate-950/70 border border-slate-800 text-slate-100 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-cyan-600/40 focus:border-slate-700 disabled:opacity-50 disabled:cursor-not-allowed transition-all shadow-inner shadow-black/30"
            />
          </div>

          {/* Send */}
          <button
            onClick={handleSendMessage}
            disabled={!messageText.trim() || !selectedPlayer}
            className="px-4 py-3 rounded-xl bg-gradient-to-r from-cyan-600 to-blue-600 hover:from-cyan-500 hover:to-blue-500 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2 shadow-lg shadow-cyan-900/20"
            title="Send"
          >
            <Send className="w-5 h-5" />
            <span className="hidden sm:inline text-sm font-semibold">Send</span>
          </button>
        </div>

        {isTyping && selectedPlayer && (
          <div className="text-[11px] text-slate-400 mt-2">You are typing...</div>
        )}

        {showEmojiPicker && (
          <EmojiPicker
            onEmojiSelect={handleEmojiSelect}
            onGifSelect={handleGifSelect}
            onClose={() => setShowEmojiPicker(false)}
          />
        )}
      </div>
    </div>
  );
};

export default ChatInterface;


import React, { useEffect, useMemo, useRef, useState } from 'react';
import { Reply, Copy, ThumbsUp, ThumbsDown, Trash2, X } from 'lucide-react';
import { Message } from '../../types';

type Reaction = 'up' | 'down' | null;

interface MessageItemProps {
  message: Message & { my_reaction?: Reaction };
  prevMessage: Message | null;
  nextMessage: Message | null;
  isOwn: boolean;
  onReact: (messageId: string, reaction: Reaction) => void;
  onQuote: (message: Message) => void;
  /** קפיצה להודעה המצוטטת (אם קיימת) */
  onJumpTo?: (messageId: string) => void;
  /** הדגשה ויזואלית סביב הבועה */
  isHighlighted?: boolean;
  /** אופציונלי: כיבוי ההדגשה בלחיצה מחוץ לבועה */
  onClearHighlight?: () => void;
  currentPlayerId: string;
  /** מחיקה רכה */
  onDelete?: (messageId: string) => void;
}

/* ---------- Modal לאישור מחיקה (פנימי לקובץ) ---------- */
const ConfirmDialog: React.FC<{
  title?: string;
  message: string;
  confirmLabel?: string;
  cancelLabel?: string;
  onConfirm: () => void;
  onCancel: () => void;
}> = ({
  title = 'Delete Message',
  message,
  confirmLabel = 'Yes, delete',
  cancelLabel = 'Cancel',
  onConfirm,
  onCancel,
}) => (
  <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm">
    <div className="bg-slate-900 border border-slate-700 rounded-2xl p-6 w-80 shadow-2xl">
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-lg font-semibold text-white">{title}</h2>
        <button onClick={onCancel} className="text-slate-400 hover:text-white">
          <X className="w-5 h-5" />
        </button>
      </div>
      <p className="text-slate-300 mb-6">{message}</p>
      <div className="flex justify-end gap-2">
        <button
          onClick={onCancel}
          className="px-4 py-2 rounded-lg bg-slate-700 hover:bg-slate-600 text-slate-200 transition"
        >
          {cancelLabel}
        </button>
        <button
          onClick={onConfirm}
          className="px-4 py-2 rounded-lg bg-cyan-600 hover:bg-cyan-500 text-white shadow-lg transition"
        >
          {confirmLabel}
        </button>
      </div>
    </div>
  </div>
);

/* ---------- עזרי זמן ---------- */
function minuteKey(ts?: string) {
  if (!ts) return '';
  const d = new Date(ts);
  return `${d.getFullYear()}-${d.getMonth()}-${d.getDate()}-${d.getHours()}-${d.getMinutes()}`;
}
function sameMinute(a?: string, b?: string) {
  return !!a && !!b && minuteKey(a) === minuteKey(b);
}
function formatTime(ts: string) {
  return new Date(ts).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
}

/* ---------- עיגול פינות לפי אשכול דקה ---------- */
function roundedByCluster(isOwn: boolean, isClusterStart: boolean, isClusterEnd: boolean) {
  if (!isClusterStart && !isClusterEnd) return 'rounded-md';
  if (isClusterStart && isClusterEnd) {
    return isOwn
      ? 'rounded-md rounded-tr-2xl rounded-br-2xl'
      : 'rounded-md rounded-tl-2xl rounded-bl-2xl';
  }
  if (isClusterStart) return isOwn ? 'rounded-md rounded-tr-2xl' : 'rounded-md rounded-tl-2xl';
  return isOwn ? 'rounded-md rounded-br-2xl' : 'rounded-md rounded-bl-2xl';
}

const MessageItem: React.FC<MessageItemProps> = ({
  message,
  prevMessage,
  nextMessage,
  isOwn,
  onReact,
  onQuote,
  onJumpTo,
  isHighlighted = false,
  onClearHighlight,
  currentPlayerId,
  onDelete,
}) => {
  const [hover, setHover] = useState(false);
  const bubbleRef = useRef<HTMLDivElement>(null);

  // מודל מחיקה
  const [confirmVisible, setConfirmVisible] = useState(false);
  const [pendingDeleteId, setPendingDeleteId] = useState<string | null>(null);
  const openDeleteConfirm = (id: string) => {
    setPendingDeleteId(id);
    setConfirmVisible(true);
  };
  const confirmDelete = () => {
    if (pendingDeleteId) onDelete?.(pendingDeleteId);
    setConfirmVisible(false);
    setPendingDeleteId(null);
  };
  const cancelDelete = () => {
    setConfirmVisible(false);
    setPendingDeleteId(null);
  };

  const isBot = message.type === 'bot';
  const isDeleted = !!(message as any).deleted;
  const canReact = !isOwn && !isBot && !!currentPlayerId && !isDeleted;
  const canCopy = !isDeleted;
  const canQuote = !isDeleted;
  const myReaction: Reaction = message.my_reaction ?? null;

  const safeMessageId =
    message.id || `${message.timestamp}|${message.from}|${message.message ?? ''}`;

  // תחילת/סוף אשכול ע"פ דקה ושולח
  const isClusterStart = useMemo(() => {
    if (!prevMessage) return true;
    const sameSender = prevMessage.from === message.from;
    return !(sameSender && sameMinute(prevMessage.timestamp, message.timestamp));
  }, [prevMessage, message]);

  const isClusterEnd = useMemo(() => {
    if (!nextMessage) return true;
    const sameSender = nextMessage.from === message.from;
    return !(sameSender && sameMinute(nextMessage.timestamp, message.timestamp));
  }, [nextMessage, message]);

  const showTimeHeader = isClusterStart;

  // צבעי בועה
  const surface = isOwn
    ? 'bg-gradient-to-r from-cyan-600 to-blue-600 text-white'
    : isBot
    ? 'bg-gradient-to-r from紫-600 to-violet-600 text-white'
    : 'bg-slate-700 text-white';

  const bubbleRound = roundedByCluster(isOwn, isClusterStart, isClusterEnd);

  // מסגרת הדגשה אופציונלית (רק סביב הבועה)
  const highlightRing = isHighlighted
    ? 'ring-2 ring-cyan-400/90 ring-offset-2 ring-offset-slate-900'
    : '';

  // סגירת ההדגשה בלחיצה מחוץ לבועה (מופעל רק כשהודגש)
  useEffect(() => {
    if (!isHighlighted) return;

    const handleClick = (e: MouseEvent) => {
      const target = e.target as Node | null;
      if (!bubbleRef.current) return;
      if (target && bubbleRef.current.contains(target)) return; // קליק בתוך הבועה – לא מנקים
      onClearHighlight?.();
    };

    document.addEventListener('mousedown', handleClick, true);
    return () => document.removeEventListener('mousedown', handleClick, true);
  }, [isHighlighted, onClearHighlight]);

  const bubbleClasses = [
    'relative inline-block max-w-full px-3 py-2 text-sm leading-snug break-words shadow-md',
    surface,
    bubbleRound,
    highlightRing,
    isDeleted ? 'opacity-70 italic' : '',
  ].join(' ');

  const rowClasses = `group flex ${isOwn ? 'justify-end' : 'justify-start'}`;

  const toggle = (choice: Exclude<Reaction, null>) => {
    if (!canReact) return;
    onReact(safeMessageId, myReaction === choice ? null : choice);
  };

  const copyToClipboard = (text: string) => navigator.clipboard.writeText(text);

  // טקסט להצגה (מחיקה רכה => placeholder)
  const displayText = isDeleted ? 'Message deleted' : (message.message ?? '');

  // טקסט לציטוט (אם המצוטט נמחק)
  const quotedIsDeleted = !!message.quoted_message?.deleted;
  const quotedPreviewText = quotedIsDeleted
    ? 'Message deleted'
    : (message.quoted_message?.message ?? '');

  return (
    <>
      <div className="space-y-px" id={`msg-${safeMessageId}`}>
        {showTimeHeader && (
          <div
            className={`text-[11px] text-slate-400 px-1 ${
              isOwn ? 'text-right pr-3' : 'text-left pl-3'
            }`}
          >
            {formatTime(message.timestamp)}
          </div>
        )}

        <div
          className={rowClasses}
          onMouseEnter={() => setHover(true)}
          onMouseLeave={() => setHover(false)}
        >
          <div className="relative">
            {/* הבועה (עם מזהה ו-ref כדי להדגיש רק אותה ולזהות קליקים מחוץ) */}
            <div
              id={`bubble-${safeMessageId}`}
              ref={bubbleRef}
              className={bubbleClasses}
            >
              {/* תיבת ציטוט (אם קיימת) - לחיצה קופצת להודעה המקורית */}
              {message.quoted_message && (
                <button
                  type="button"
                  onClick={() =>
                    message.quoted_message?.id && onJumpTo?.(message.quoted_message.id)
                  }
                  className="mb-2 w-full text-left p-2 border-l-4 border-slate-600 bg-slate-800/50 rounded-r-lg
                             hover:bg-slate-700/50 transition focus:outline-none focus:ring-2 focus:ring-cyan-500/40"
                >
                  <div className="flex items-center gap-1 text-[11px] text-slate-300 mb-0.5">
                    <Reply className="w-3.5 h-3.5" />
                    <span>Replying to {message.quoted_message.from}</span>
                  </div>
                  <div className="text-sm text-slate-100 line-clamp-1">
                    {quotedPreviewText}
                  </div>
                </button>
              )}

              {/* טקסט ההודעה */}
              {displayText}
            </div>

            {/* Badge לייק/דיסלייק קטן */}
            {myReaction && (
              <span
                className="
                  absolute top-1/2 left-0 -translate-x-1/2 -translate-y-1/2
                  rounded-full border bg-slate-900/70 p-0.5 shadow border-cyan-400/30
                "
                title={myReaction === 'up' ? 'You liked this' : 'You disliked this'}
              >
                {myReaction === 'up' ? (
                  <ThumbsUp className="w-3 h-3 text-cyan-300" />
                ) : (
                  <ThumbsDown className="w-3 h-3 text-rose-300" />
                )}
              </span>
            )}

            {/* תפריט פעולות צף */}
            <div
              className={`
                absolute top-0 ${isOwn ? 'right-3' : 'left-3'}
                -translate-y-full mt-1
                opacity-0 pointer-events-none z-10
                transition-opacity duration-150
                ${hover ? 'opacity-100 pointer-events-auto' : ''}
              `}
            >
              <div className="flex items-center gap-1 bg-slate-900/80 backdrop-blur px-2 py-1.5 rounded-2xl border border-slate-700 shadow-xl">
                {canReact && (
                  <>
                    <button
                      onClick={() => toggle('up')}
                      className={`p-1 rounded-md ${
                        myReaction === 'up'
                          ? 'text-cyan-300 ring-1 ring-cyan-400/40 bg-white/5'
                          : 'text-slate-300 hover:bg-white/5'
                      }`}
                      aria-label={myReaction === 'up' ? 'Remove like' : 'Like'}
                      title={myReaction === 'up' ? 'Liked' : 'Like'}
                    >
                      <ThumbsUp className="w-4 h-4" />
                    </button>

                    <button
                      onClick={() => toggle('down')}
                      className={`p-1 rounded-md ${
                        myReaction === 'down'
                          ? 'text-rose-300 ring-1 ring-rose-400/40 bg-white/5'
                          : 'text-slate-300 hover:bg-white/5'
                      }`}
                      aria-label={myReaction === 'down' ? 'Remove dislike' : 'Dislike'}
                      title={myReaction === 'down' ? 'Disliked' : 'Dislike'}
                    >
                      <ThumbsDown className="w-4 h-4" />
                    </button>
                  </>
                )}

                <button
                  onClick={() => canQuote && onQuote(message)}
                  disabled={!canQuote}
                  className={`p-1 rounded-md ${canQuote ? 'text-slate-300 hover:text-cyan-300 hover:bg-white/5' : 'text-slate-500 cursor-not-allowed'}`}
                  aria-label="Quote"
                  title={canQuote ? 'Quote' : 'Cannot quote deleted message'}
                >
                  <Reply className="w-4 h-4" />
                </button>

                <button
                  onClick={() => canCopy && copyToClipboard(message.message)}
                  disabled={!canCopy}
                  className={`p-1 rounded-md ${canCopy ? 'text-slate-300 hover:bg-white/5' : 'text-slate-500 cursor-not-allowed'}`}
                  aria-label="Copy"
                  title={canCopy ? 'Copy' : 'Cannot copy deleted message'}
                >
                  <Copy className="w-4 h-4" />
                </button>

                {/* מחיקה רכה – רק להודעות שלי, כל עוד לא נמחקו */}
                {isOwn && !isDeleted && onDelete && (
                  <button
                    onClick={() => openDeleteConfirm(safeMessageId)}
                    className="p-1 rounded-md text-slate-300 hover:text-rose-300 hover:bg-white/5"
                    aria-label="Delete"
                    title="Delete"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                )}
              </div>
            </div>
          </div>
        </div>

        {/* רווח אנכי דק בין הודעות */}
        <div className="h-px" />
      </div>

      {/* מודל אישור מחיקה */}
      {confirmVisible && (
        <ConfirmDialog
          message="Are you sure you want to delete this message?"
          confirmLabel="Yes, delete"
          cancelLabel="Cancel"
          onConfirm={confirmDelete}
          onCancel={cancelDelete}
        />
      )}
    </>
  );
};

export default MessageItem;


import React, { useEffect, useRef, useState } from "react";

interface MessageInputProps {
  onSubmit: (content: string) => void;
  onClose: () => void;
  onTypingStart?: () => void; 
  onTypingEnd?: () => void;   // יופעל ביציאה ממצב הקלדה
}

export const MessageInput: React.FC<MessageInputProps> = ({
  onSubmit,
  onClose,
  onTypingStart,
  onTypingEnd,
}) => {
  const [message, setMessage] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);

  useEffect(() => {
    onTypingStart?.();
    textareaRef.current?.focus();
    return () => onTypingEnd?.();
  }, [onTypingStart, onTypingEnd]);

  const handleSubmit = (e?: React.FormEvent) => {
    e?.preventDefault();
    const val = message.trim();
    if (!val) return;
    onSubmit(val);
    setMessage("");
    onClose();
  };

  const handleKeyDown: React.KeyboardEventHandler<HTMLTextAreaElement> = (e) => {
    e.stopPropagation();
    if (e.key === "Escape") {
      e.preventDefault();
      onClose();
      return;
    }
    if ((e.key === "Enter" && (e.ctrlKey || e.metaKey))) {
      e.preventDefault();
      handleSubmit();
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div
        className="absolute inset-0 bg-black/40"
        onClick={onClose}
      />
      <div className="relative bg-white rounded-xl shadow-2xl p-6 w-96 animate-scale-in">
        <div className="flex justify-between items-center mb-4">
          <h3 className="text-lg font-semibold text-gray-800">Leave a Message 📝</h3>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600" aria-label="Close">
            ✕
          </button>
        </div>
        <form onSubmit={handleSubmit}>
          <textarea
            ref={textareaRef}
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Write your message here... ✨"
            className="w-full p-3 border rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 min-h-[100px] text-black placeholder-gray-400"
          />
          <div className="flex justify-end mt-4 gap-2">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-gray-600 hover:bg-gray-100 rounded-lg"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={!message.trim()}
              className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
            >
              Send
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

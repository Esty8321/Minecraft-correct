

import React, { useEffect, useRef, useState } from 'react';
import { Smile, Image, Search, X } from 'lucide-react';

interface EmojiPickerProps {
  onEmojiSelect: (emoji: string) => void;
  onGifSelect: (gifUrl: string) => void;
  onClose: () => void;
}

type Tab = 'emoji' | 'gif';

const EmojiPicker: React.FC<EmojiPickerProps> = ({ onEmojiSelect, onGifSelect, onClose }) => {
  const [activeTab, setActiveTab] = useState<Tab>('emoji');
  const [searchTerm, setSearchTerm] = useState('');
  const boxRef = useRef<HTMLDivElement>(null);

  // רשימת אימוג'ים (כמו אצלך)
  const emojis = [
    '😀','😃','😄','😁','😆','😅','😂','🤣','😊','😇',
    '🙂','🙃','😉','😌','😍','🥰','😘','😗','😙','😚',
    '😋','😛','😝','😜','🤪','🤨','🧐','🤓','😎','🤩',
    '🥳','😏','😒','😞','😔','😟','😕','🙁','☹️','😣',
    '😖','😫','😩','🥺','😢','😭','😤','😠','😡','🤬',
    '🤯','😳','🥵','🥶','😱','😨','😰','😥','😓','🤗',
    '🤔','🤭','🤫','🤥','😶','😐','😑','😬','🙄','😯',
    '👍','👎','👌','✌️','🤞','🤟','🤘','🤙','👈','👉',
    '👆','👇','☝️','✋','🤚','🖐️','🖖','👋','🤝','👏',
    '🙌','👐','🤲','🙏','✍️','💪','🦾','🦿','🦵','🦶',
    '🎮','🎯','🎲','🎪','🎭','🎨','🎬','🎤','🎧','🎼',
    '🔥','💯','💥','💫','⭐','🌟','✨','⚡','💎','🏆'
  ];

  const gameGifs = [
    'https://media.giphy.com/media/3o7abKhOpu0NwenH3O/giphy.gif',
    'https://media.giphy.com/media/26AHPxxnSw1L9T1rW/giphy.gif',
    'https://media.giphy.com/media/3oriNYQX2lC6dfW2Ji/giphy.gif',
    'https://media.giphy.com/media/l46Cy1rHbQ92uuLXa/giphy.gif',
    'https://media.giphy.com/media/3o6fIS7RIjRZOUFRhK/giphy.gif',
    'https://media.giphy.com/media/26AHICv4otlZ0ruGk/giphy.gif'
  ];

  const filteredEmojis = emojis.filter((emoji) =>
    searchTerm.trim() === '' ? true : emoji.includes(searchTerm.trim())
  );

  // סגירה ב-Escape
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [onClose]);

  return (
    <div
      ref={boxRef}
      className="absolute bottom-16 left-4 right-4 bg-slate-800 border border-slate-600 rounded-xl shadow-2xl z-50 max-h-96 flex flex-col"
      // חשוב: קליקים/לחיצות בתוך הפיקר לא יבעברו החוצה (כדי שמאזין 'click outside' של ההורה לא יסגור)
      onMouseDown={(e) => { e.stopPropagation(); }}
      onClick={(e) => { e.stopPropagation(); }}
    >
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-slate-600">
        <div className="flex gap-2">
          <button
            onClick={(e) => { e.stopPropagation(); setActiveTab('emoji'); }}
            className={`
              px-4 py-2 rounded-lg transition-all duration-200 flex items-center gap-2
              ${activeTab === 'emoji'
                ? 'bg-cyan-600 text-white'
                : 'text-slate-300 hover:text-white hover:bg-slate-700'
              }
            `}
          >
            <Smile className="w-4 h-4" />
            Emojis
          </button>
          <button
            onClick={(e) => { e.stopPropagation(); setActiveTab('gif'); }}
            className={`
              px-4 py-2 rounded-lg transition-all duration-200 flex items-center gap-2
              ${activeTab === 'gif'
                ? 'bg-cyan-600 text-white'
                : 'text-slate-300 hover:text-white hover:bg-slate-700'
              }
            `}
          >
            <Image className="w-4 h-4" />
            GIFs
          </button>
        </div>
        <button
          onClick={(e) => { e.stopPropagation(); onClose(); }}
          className="p-2 text-slate-400 hover:text-white hover:bg-slate-700 rounded-lg transition-colors"
          aria-label="Close emoji picker"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* Search */}
      {activeTab === 'emoji' && (
        <div className="p-4 border-b border-slate-600">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400 pointer-events-none" />
            <input
              type="text"
              placeholder="Search emojis..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              onClick={(e) => e.stopPropagation()}
              onMouseDown={(e) => e.stopPropagation()}
              className="w-full pl-10 pr-4 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white placeholder-slate-400 focus:outline-none focus:border-cyan-500"
            />
          </div>
        </div>
      )}

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-4">
        {activeTab === 'emoji' ? (
          <div className="grid grid-cols-8 gap-2">
            {filteredEmojis.map((emoji, index) => (
              <button
                key={index}
                // preventDefault: לא לאבד פוקוס לאינפוט; stopPropagation: לא לסגור את הפיקר
                onMouseDown={(e) => { e.preventDefault(); e.stopPropagation(); }}
                onClick={(e) => { e.stopPropagation(); onEmojiSelect(emoji); }}
                className="p-2 text-2xl hover:bg-slate-700 rounded-lg transition-colors"
                aria-label={`Insert ${emoji}`}
              >
                {emoji}
              </button>
            ))}
          </div>
        ) : (
          <div className="grid grid-cols-2 gap-3">
            {gameGifs.map((gif, index) => (
              <button
                key={index}
                onMouseDown={(e) => { e.preventDefault(); e.stopPropagation(); }}
                onClick={(e) => { e.stopPropagation(); onGifSelect(gif); }}
                className="cursor-pointer rounded-lg overflow-hidden hover:ring-2 hover:ring-cyan-500 transition-all duration-200"
                aria-label="Insert GIF"
              >
                <img
                  src={gif}
                  alt="GIF"
                  className="w-full h-24 object-cover"
                  loading="lazy"
                />
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default EmojiPicker;

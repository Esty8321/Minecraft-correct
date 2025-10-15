import React from 'react';

interface MessageBubbleProps {
  message: {
    content: string;
    author: string;
    timestamp: string;
  };
}

export const MessageBubble: React.FC<MessageBubbleProps> = ({ message }) => {
  return (
    <div className="fixed bottom-4 right-4 max-w-sm bg-white rounded-lg shadow-lg p-4 border border-blue-200 animate-fade-in">
      <div className="flex items-start space-x-2">
        <span className="text-2xl">💌</span>
        <div>
          <p className="text-black font-medium text-sm">{message.author}</p>
          <p className="text-black font-normal mt-1">{message.content}</p>
          <p className="text-gray-600 text-xs mt-2">
            {new Date(message.timestamp).toLocaleString()}
          </p>
        </div>
      </div>
    </div>
  );
};
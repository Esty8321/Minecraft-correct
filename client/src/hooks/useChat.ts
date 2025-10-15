import { useState, useEffect } from 'react';
import { ChatTheme } from '../types';

export const defaultThemes: ChatTheme[] = [
  {
    name: 'Cyber Blue',
    primaryColor: '#0ea5e9',
    secondaryColor: '#06b6d4',
    accentColor: '#3b82f6',
    backgroundColor: '#0f172a',
    cardColor: '#1e293b',
    textColor: '#f8fafc'
  },
  {
    name: 'Neon Purple',
    primaryColor: '#a855f7',
    secondaryColor: '#c084fc',
    accentColor: '#8b5cf6',
    backgroundColor: '#1a1625',
    cardColor: '#2d1b42',
    textColor: '#f3e8ff'
  },
  {
    name: 'Matrix Green',
    primaryColor: '#22c55e',
    secondaryColor: '#16a34a',
    accentColor: '#15803d',
    backgroundColor: '#0a0f0a',
    cardColor: '#1a2e1a',
    textColor: '#dcfce7'
  },
  {
    name: 'Gaming Red',
    primaryColor: '#ef4444',
    secondaryColor: '#f87171',
    accentColor: '#dc2626',
    backgroundColor: '#1c1917',
    cardColor: '#3c2e2a',
    textColor: '#fef2f2'
  }
];

type UseChatReturn = {
  currentTheme: ChatTheme;
  defaultThemes: ChatTheme[];
  showCustomization: boolean;
  setShowCustomization: (v: boolean) => void;
  showEmojiPicker: boolean;
  setShowEmojiPicker: (v: boolean) => void;
  changeTheme: (theme: ChatTheme) => void;
};

export const useChat = (): UseChatReturn => {
  const [currentTheme, setCurrentTheme] = useState<ChatTheme>(defaultThemes[0]);
  const [showCustomization, setShowCustomization] = useState(false);
  const [showEmojiPicker, setShowEmojiPicker] = useState(false);

  useEffect(() => {
    const savedTheme = localStorage.getItem('chat-theme');
    if (savedTheme) {
      try {
        setCurrentTheme(JSON.parse(savedTheme));
      } catch (error) {
        console.error('Error loading saved theme:', error);
      }
    }
  }, []);

  const changeTheme = (theme: ChatTheme) => {
    setCurrentTheme(theme);
    localStorage.setItem('chat-theme', JSON.stringify(theme));
    // Apply CSS variables
    const root = document.documentElement;
    root.style.setProperty('--primary-color', theme.primaryColor);
    root.style.setProperty('--secondary-color', theme.secondaryColor);
    root.style.setProperty('--accent-color', theme.accentColor);
    root.style.setProperty('--bg-color', theme.backgroundColor);
    root.style.setProperty('--card-color', theme.cardColor);
    root.style.setProperty('--text-color', theme.textColor);
  };

  return {
    currentTheme,
    defaultThemes,
    showCustomization,
    setShowCustomization,
    showEmojiPicker,
    setShowEmojiPicker,
    changeTheme
  };
};

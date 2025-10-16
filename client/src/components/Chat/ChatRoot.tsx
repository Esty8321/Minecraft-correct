import React, { useEffect, useState } from "react";
import { X } from "lucide-react";
import { useWebSocket } from "../../hooks/useWebSocket";
import Sidebar from "./Sidebar";
import ChatInterface from "./ChatInterface";
import CustomizationPanel from "./CustomizationPanel";
import type { ChatTheme } from "../../types";

interface ChatRootProps {
    onClose?: () => void;
}

const ChatRoot: React.FC<ChatRootProps> = ({ onClose }) => {
    // --- WebSocket & chat logic ---
    const {
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
    } = useWebSocket();


    // --- Themes (matching ChatTheme interface from your index.ts) ---
    const themes: ChatTheme[] = [
        {
            name: "Dark Mode",
            primaryColor: "#0f172a",
            secondaryColor: "#1e293b",
            accentColor: "#06b6d4",
            backgroundColor: "#020617",
            cardColor: "#1e293b",
            textColor: "#f8fafc",
        },
        {
            name: "Light Mode",
            primaryColor: "#f8fafc",
            secondaryColor: "#e2e8f0",
            accentColor: "#0ea5e9",
            backgroundColor: "#ffffff",
            cardColor: "#f1f5f9",
            textColor: "#0f172a",
        },
        {
            name: "Forest",
            primaryColor: "#14532d",
            secondaryColor: "#166534",
            accentColor: "#22c55e",
            backgroundColor: "#0f172a",
            cardColor: "#1e293b",
            textColor: "#d1fae5",
        },
        {
            name: "Neon",
            primaryColor: "#06b6d4",
            secondaryColor: "#67e8f9",
            accentColor: "#f0f",
            backgroundColor: "#0f172a",
            cardColor: "#1e293b",
            textColor: "#f9fafb",
        },
    ];

    const [currentTheme, setCurrentTheme] = useState<ChatTheme>(themes[0]);
    const [showCustomization, setShowCustomization] = useState(false);
    const [showEmojiPicker, setShowEmojiPicker] = useState(false);

    return (
        <div
            className="relative flex h-full w-full overflow-hidden"
            style={{
                backgroundColor: currentTheme.backgroundColor,
                color: currentTheme.textColor,
            }}
        >
            {/* ---- Sidebar ---- */}
            <Sidebar
                activePlayers={activePlayers}
                selectedPlayer={selectedPlayer}
                onSelectPlayer={selectPlayer}
                currentPlayerId={currentPlayerId || ""}
                unreadCounts={unreadCounts}
                onMarkRead={markRead}
            />

            {/* ---- Main Chat Interface ---- */}
            <ChatInterface
                messages={messages}
                selectedPlayer={selectedPlayer}
                currentPlayerId={currentPlayerId || ""}
                onSendMessage={sendMessage}
                onReactMessage={reactToMessage}   // ✅ correct name
                onDeleteMessage={deleteMessage}   // ✅ soft delete
                showEmojiPicker={showEmojiPicker}
                setShowEmojiPicker={setShowEmojiPicker}
                onCustomizationToggle={() => setShowCustomization(true)}
                onMarkRead={markRead}
            />

            {/* ---- Top-right buttons ---- */}
            <div className="absolute top-3 right-3 flex gap-2 z-40">
                {/* 🎨 Theme button */}
                <button
                    onClick={() => setShowCustomization((prev) => !prev)}
                    className="bg-slate-700 hover:bg-slate-600 p-2 rounded-full transition-all"
                    title="Customize Chat"
                >
                    🎨
                </button>

                {/* ❌ Close button */}
                {onClose && (
                    <button
                        onClick={onClose}
                        className="bg-slate-700 hover:bg-slate-600 p-2 rounded-full transition-all"
                        title="Close chat"
                    >
                        <X size={18} />
                    </button>
                )}
            </div>

            {/* ---- Customization Panel ---- */}
            {showCustomization && (
                <CustomizationPanel
                    currentTheme={currentTheme}
                    themes={themes}
                    onThemeChange={setCurrentTheme}
                    onClose={() => setShowCustomization(false)}
                />
            )}
        </div>
    );
};

export default ChatRoot;

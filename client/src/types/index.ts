export type Reaction = 'up' | 'down' | null

// ===== Player =====
export interface Player {
  id: string
  username: string
  email: string
  avatar?: string
  is_active: boolean            // לשימוש /active-players
  level?: number
  status?: 'online' | 'in-game' | 'away'
}

// ===== Messages =====
//
// הערות:
// - quoted_message: ההודעה שמצטטים (אם קיימת).
// - my_reaction: התגובה הפרטית שלי (לא גלויה לצד השני).
// - read_by: מי כבר קרא (לעזרים UI).
// - deleted: למחיקה רכה (soft-delete). כשtrue הלקוח מציג "Message deleted" ותוכן ההודעה ריק.
// - updated_at: זמן עדכון אחרון (למשל לאחר מחיקה רכה).
export interface Message {
  id: string                    // בד"כ נבנה כ: ts|from|text (שרת/לקוח)
  from: string                  // מזהה השולח (playerId)
  to: string                    // מזהה הנמען (playerId)
  message: string               // תוכן ההודעה
  timestamp: string             // ISO string
  type: 'user' | 'bot'
  quoted_message?: Message
  read_by?: string[]
  my_reaction?: Reaction
  deleted?: boolean             // NEW: soft delete flag
  updated_at?: string           // NEW: last update (ISO)
}

// ===== Theme =====
export interface ChatTheme {
  name: string
  primaryColor: string
  secondaryColor: string
  accentColor: string
  backgroundColor: string
  cardColor: string
  textColor: string
}

// ===== WebSocket Protocol (logical) =====
//
// הערות:
// - הלקוח שולח type:'message' עם selectedPlayer (היעד) ואופציונלית quotedId.
// - השרת יכול להחזיר הודעות עם quoted_message משורשרת, או רק עם messageId בהתראות ריאקציה.
// - type:'read' מסמן לשרת שסימנו שיחה עם with כנקראה.
// - type:'unread' מהשרת מעדכן מונים מקומיים.
// - NEW: type:'delete' (לקוח->שרת) למחיקה רכה; type:'message_updated' (שרת->לקוח) לעדכון הודעה שנמחקה רך.
export type WSMessageType =
  | 'select'
  | 'message'
  | 'react'          // תגובה פרטית ל-msg (up/down/null)
  | 'typing'
  | 'history'
  | 'sent'
  | 'error'
  | 'read'           // הלקוח -> שרת: סימון שנקרא
  | 'unread'         // שרת -> לקוח: עדכון מונים
  | 'delete'         // NEW: client -> server (soft delete)
  | 'message_updated'// NEW: server -> clients (after soft delete)

export interface WebSocketMessage {
  type: WSMessageType

  // --- select ---
  selectedPlayer?: string        // יעד השיחה שנבחר (playerId)

  // --- message ---
  message?: string               // טקסט ההודעה
  timestamp?: string             // זמן ההודעה
  sender?: string                // מזהה השולח כפי שהשרת משדר חזרה
  to?: string                    // יעד כפי שהשרת עשוי לשדר
  quotedId?: string              // מזהה ההודעה המצוטטת כשהלקוח שולח

  // --- react ---
  messageId?: string             // מזהה ההודעה אליה מגיבים
  reaction?: Reaction            // 'up' | 'down' | null

  // --- history ---
  with?: string                  // עם מי ההיסטוריה / למי סימנו read
  messages?: Message[]           // היסטוריה מלאה (עשויה לכלול my_reaction)

  // --- unread (server -> client) ---
  from?: string                  // ממי ההודעות הלא-נקראו (מקור)
  count?: number                 // כמות הודעות לא-נקראו (from -> to)

  // --- error ---
  message_error?: string         // תיאור שגיאה אם type==='error'

  // --- message_updated (server -> client) ---
  // תכולת ההודעה המעודכנת כפי שהשרת משדר בעת מחיקה רכה.
  updated_message?: {
    id: string
    from?: string
    to?: string
    deleted?: boolean
    text?: string                // בשרת שלי זה נשלח כשדה "text": "" לאחר מחיקה
    updated_at?: string
  }

  // כלליים
  data?: any
}

// טיפוסים ייעודיים (נוחים לשימוש פנימי אם צריך)
export interface UnreadPayload {
  type: 'unread'
  from: string
  to: string
  count: number
}

export interface ReadPayload {
  type: 'read'
  with: string
}

// NEW: מחיקה רכה (client -> server)
export interface DeletePayload {
  type: 'delete'
  messageId: string
}

// NEW: עדכון הודעה (server -> client) אחרי מחיקה רכה
export interface MessageUpdatedPayload {
  type: 'message_updated'
  message: {
    id: string
    from?: string
    to?: string
    deleted: boolean
    text: string
    updated_at?: string
  }
}

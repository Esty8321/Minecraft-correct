// import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
// import type { Message as ChatMessage, Player, WebSocketMessage, Reaction } from '../types'
// import { authStorage } from '../utils/auth'

// /** בניית כתובות לשרת (תומך localhost/דומיין) */
// function backendHost(): string {
//   const h = window.location.hostname
//   return (h === 'localhost' || h === '127.0.0.1') ? '127.0.0.1' : h
// }
// function wsUrl(): string {
//   const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
//   return `${proto}//${backendHost()}:8000/ws`///??
// }
// function apiBase(): string {
//   const http = window.location.protocol === 'https:' ? 'https:' : 'http:'
//   return `${http}//${backendHost()}:8000`
// }

// type UseWS = {
//   isConnected: boolean
//   messages: ChatMessage[]
//   selectedPlayer: Player | null
//   selectPlayer: (p: Player) => void
//   sendMessage: (text: string, quotedMessage?: ChatMessage) => void
//   reactToMessage: (id: string, reaction: Reaction) => void
//   /** NEW: מחיקה רכה של הודעה שלי */
//   deleteMessage: (messageId: string) => void
//   activePlayers: Player[]
//   currentPlayerId?: string
//   unreadCounts: Record<string, number>
//   markRead: (playerId: string) => void
// }

// export function useWebSocket(): UseWS {
//   const socketRef = useRef<WebSocket | null>(null)

//   const [isConnected, setIsConnected] = useState(false)
//   const [messages, setMessages] = useState<ChatMessage[]>([])
//   const [activePlayers, setActivePlayers] = useState<Player[]>([])
//   const [selectedPlayer, _setSelectedPlayer] = useState<Player | null>(null)
//   const [currentPlayerId, _setCurrentPlayerId] = useState<string>()
//   const [unreadCounts, setUnreadCounts] = useState<Record<string, number>>({})

//   // refs לשימוש בתוך ה-handlers
//   const selectedPlayerRef = useRef<Player | null>(null)
//   const currentPlayerIdRef = useRef<string | undefined>(undefined)
//   const seenIdsRef = useRef<Set<string>>(new Set())

//   // אינדקס הודעות לפי id לשחזור quoted_message
//   const messageIndexRef = useRef<Map<string, ChatMessage>>(new Map())

//   const setSelectedPlayer = useCallback((p: Player | null) => {
//     selectedPlayerRef.current = p
//     _setSelectedPlayer(p)
//   }, [])
//   const setCurrentPlayerId = useCallback((id?: string) => {
//     currentPlayerIdRef.current = id
//     _setCurrentPlayerId(id)
//   }, [])

//   /** משחזר quoted_message אם יש quotedId ויש לנו את ההודעה המקורית */
//   const attachQuoteIfAny = useCallback((raw: any): ChatMessage => {
//     if (raw?.quoted_message && typeof raw.quoted_message === 'object') {
//       return raw as ChatMessage
//     }
//     const quotedId = raw?.quotedId || raw?.quoted_id
//     if (quotedId) {
//       const q = messageIndexRef.current.get(quotedId)
//       if (q) return { ...(raw as ChatMessage), quoted_message: q } as any
//     }
//     return raw as ChatMessage
//   }, [])

//   /** מוסיף/מעדכן הודעות + מעדכן האינדקס, כולל שזירת הציטוט */
//   const upsertMessages = useCallback((list: ChatMessage[]) => {
//     const withQuotes = list.map(attachQuoteIfAny)
//     setMessages(prev => {
//       const next = [...prev]
//       for (const m of withQuotes) {
//         if (!seenIdsRef.current.has(m.id)) {
//           next.push(m)
//           seenIdsRef.current.add(m.id)
//         } else {
//           const i = next.findIndex(x => x.id === m.id)
//           if (i >= 0) next[i] = { ...next[i], ...m }
//         }
//       }
//       return next
//     })
//     for (const m of withQuotes) {
//       messageIndexRef.current.set(m.id, m)
//     }
//   }, [attachQuoteIfAny])

//   // -------- WebSocket (נפתח פעם אחת) --------
//   useEffect(() => {
//     const url = wsUrl()
//     const ws = new WebSocket(url)
//     socketRef.current = ws
//     console.log('[WS] connecting to', url)

//     ws.onopen = () => {
//       setIsConnected(true)
//       console.log('[WS] open')
//       const user = authStorage.getUser()
//       if(user?.id){
//         ws.send(JSON.stringify({player_id: user.id}))
//         setCurrentPlayerId(user.id)
//         console.log('[WS] Sent player_id', user.id)
//       }
//     }
//     ws.onerror = (e) => console.error('[WS] error', e)
//     ws.onclose = (ev) => {
//       console.warn('[WS] close', ev.code, ev.reason)
//       setIsConnected(false)
//       socketRef.current = null
//     }

//     ws.onmessage = (ev) => {
//       const data: WebSocketMessage | any = JSON.parse(ev.data)
//       const me = currentPlayerIdRef.current ?? localStorage.getItem("chat_target_id")//??
//       // --- היסטוריה ---
//       if (data.type === 'history') {
//         // const me = currentPlayerIdRef.current ?? ''
//         const sel = selectedPlayerRef.current?.id ?? ''
//         const msgs: ChatMessage[] = (data.messages ?? []).map((m: any) => {
//           const ts = m.timestamp ?? new Date().toISOString()
//           const id = m.id ?? `${ts}|${m.from}|${m.message ?? ''}`
//           const base: any = {
//             id,
//             from: m.from,
//             to: m.to ?? (m.from === me ? sel : me),
//             message: m.message ?? '',
//             timestamp: ts,
//             type: m.type === 'bot' ? 'bot' : 'user',
//             ...(Array.isArray(m.read_by) ? { read_by: m.read_by } : {}),
//             ...(m.my_reaction !== undefined ? { my_reaction: m.my_reaction } : {}),
//             ...(m.quoted_message ? { quoted_message: m.quoted_message } : {}),
//             ...(m.quotedId ? { quotedId: m.quotedId } : {}),
//             ...(m.deleted ? { deleted: true } : {}),          // NEW
//             ...(m.updated_at ? { updated_at: m.updated_at } : {}), // NEW
//           }
//           return attachQuoteIfAny(base)
//         })
//         // מחליפים רשימה מלאה (history)
//         seenIdsRef.current = new Set(msgs.map(m => m.id))
//         setMessages(msgs)
//         for (const m of msgs) messageIndexRef.current.set(m.id, m)
//         return
//       }

//       // --- הודעה חדשה ---
//       if (data.type === 'message') {
//         const ts: string = data.timestamp ?? new Date().toISOString()
//         const sender: string = data.sender ?? 'unknown'
//         const id = data.id ?? `${ts}|${sender}|${data.message ?? ''}`
//         if (seenIdsRef.current.has(id)) return

//         const me = currentPlayerIdRef.current ?? ''
//         const sel = selectedPlayerRef.current?.id ?? ''
//         const toComputed = (data as any).to ?? (sender === me ? sel : me)

//         const raw: any = {
//           id,
//           from: sender,
//           to: toComputed,
//           message: data.message ?? '',
//           timestamp: ts,
//           type: (data as any).isBot ? 'bot' : 'user',
//           ...(data.quoted_message ? { quoted_message: data.quoted_message } : {}),
//           ...(data.quotedId ? { quotedId: data.quotedId } : {}),
//           ...(data.deleted ? { deleted: true } : {}),                 // NEW
//           ...(data.updated_at ? { updated_at: data.updated_at } : {}),// NEW
//         }

//         const msg = attachQuoteIfAny(raw)
//         upsertMessages([msg])

//         if (toComputed === me && (!selectedPlayerRef.current || selectedPlayerRef.current.id !== sender)) {
//           setUnreadCounts(prev => ({ ...prev, [sender]: (prev[sender] || 0) + 1 }))
//         }
//         return
//       }

//       // --- ACK לריאקציה ---
//       if (data.type === 'react') {
//         const { messageId, my_reaction } = data as { messageId: string; my_reaction: Reaction }
//         setMessages(prev => prev.map(m => (m.id === messageId ? ({ ...m, my_reaction } as any) : m)))
//         const cur = messageIndexRef.current.get(messageId)
//         if (cur) messageIndexRef.current.set(messageId, { ...cur, my_reaction } as any)
//         return
//       }

//       // --- עדכון מוני לא-נקראו ---
//       if (data.type === 'unread') {
//         const me = currentPlayerIdRef.current
//         if (me && (data as any).to === me) {
//           setUnreadCounts(prev => ({ ...prev, [(data as any).from]: (data as any).count }))
//         }
//         return
//       }

//       // --- NEW: עדכון הודעה אחרי מחיקה רכה ---
//       if (data.type === 'message_updated') {
//         // השרת שלנו שולח payload.message; תומכים גם ב-updated_message לגמישות
//         const u = (data as any).message || (data as any).updated_message
//         if (!u?.id) return
//         setMessages(prev => prev.map(m => (
//           m.id === u.id
//             ? ({
//                 ...m,
//                 deleted: u.deleted ?? true,
//                 message: typeof u.text === 'string' ? u.text : '',
//                 updated_at: u.updated_at ?? m.updated_at,
//               } as any)
//             : m
//         )))
//         const cur = messageIndexRef.current.get(u.id)
//         if (cur) {
//           messageIndexRef.current.set(u.id, {
//             ...cur,
//             deleted: u.deleted ?? true,
//             message: typeof u.text === 'string' ? u.text : '',
//             updated_at: u.updated_at ?? cur.updated_at,
//           } as any)
//         }
//         return
//       }

//       if (data.type === 'typing' || data.type === 'sent') return
//       console.warn('Unhandled WS message:', data)
//     }

//     return () => { try { ws.close() } catch {} }
//   }, [attachQuoteIfAny, upsertMessages])

//   // -------- מי אני --------
//   useEffect(() => {
//     const token = new URLSearchParams(window.location.search).get('token') ?? ''
//     if (!token) return
//     fetch(`${apiBase()}/whoami?token=${encodeURIComponent(token)}`)
//       .then(r => r.json())
//       .then(d => { if (d?.ok) setCurrentPlayerId(d.player_id) })
//       .catch(() => {})
//   }, [setCurrentPlayerId])

//   // -------- אתחול מוני unread --------
//   useEffect(() => {
//     const token = new URLSearchParams(window.location.search).get('token') ?? ''
//     if (!token) return
//     let stop = false
//     async function initUnread() {
//       try {
//         const res = await fetch(`${apiBase()}/unread-summary?token=${encodeURIComponent(token)}`)
//         const data = await res.json()
//         if (!stop && data?.ok) setUnreadCounts(data.counts || {})
//       } catch {}
//     }
//     initUnread()
//     return () => { stop = true }
//   }, [])

//   // -------- Active Players (פולינג) --------
//   useEffect(() => {
//     let stop = false
//     const tick = async () => {
//       try {
//         const res = await fetch(`${apiBase()}/active-players`)
//         const data = await res.json()
//         if (!stop) setActivePlayers(data)
//       } catch {}
//     }
//     tick()
//     const id = setInterval(tick, 3000)
//     return () => { stop = true; clearInterval(id) }
//   }, [])

//   // -------- פעולות --------
//   const selectPlayer = useCallback((p: Player) => {
//     setSelectedPlayer(p)
//     const ws = socketRef.current
//     if (!ws || ws.readyState !== WebSocket.OPEN) return

//     ws.send(JSON.stringify({ type: 'select', selectedPlayer: p.id }))
//     ws.send(JSON.stringify({ type: 'read', with: p.id }))

//     setUnreadCounts(prev => ({ ...prev, [p.id]: 0 }))
//   }, [setSelectedPlayer])

//   const markRead = useCallback((playerId: string) => {
//     const ws = socketRef.current
//     if (!ws || ws.readyState !== WebSocket.OPEN) return
//     ws.send(JSON.stringify({ type: 'read', with: playerId }))
//     setUnreadCounts(prev => ({ ...prev, [playerId]: 0 }))
//   }, [])

//   const sendMessage = useCallback((text: string, quotedMessage?: ChatMessage) => {
//     const ws = socketRef.current
//     const sel = selectedPlayerRef.current
//     const me = currentPlayerIdRef.current
//     if (!ws || ws.readyState !== WebSocket.OPEN) return
//     if (!sel || !me) return
//     if (!text.trim()) return

//     const ts = new Date().toISOString()
//     const id = `${ts}|${me}|${text}`

//     // חשוב: cast ל-any כדי לא לקבל אזהרה אם WebSocketMessage לא כולל quotedId בטיפוסים
//     const payload: any = {
//       type: 'message',
//       message: text,
//       selectedPlayer: sel.id,
//       timestamp: ts,
//       ...(quotedMessage ? { quotedId: quotedMessage.id } : {}),
//     }
//     ws.send(JSON.stringify(payload))

//     // עדכון Optimistic כולל הציטוט
//     const optimistic: ChatMessage = {
//       id,
//       from: me,
//       to: sel.id,
//       message: text,
//       timestamp: ts,
//       type: 'user',
//       ...(quotedMessage ? { quoted_message: quotedMessage } : {}),
//     } as any
//     seenIdsRef.current.add(id)
//     messageIndexRef.current.set(id, optimistic)
//     setMessages(prev => [...prev, optimistic])
//   }, [])

//   const reactToMessage = useCallback((messageId: string, reaction: Reaction) => {
//     const ws = socketRef.current
//     if (!ws || ws.readyState !== WebSocket.OPEN) return

//     const me = currentPlayerIdRef.current
//     const target = messageIndexRef.current.get(messageId)
//     if (target && target.from === me) return

//     ws.send(JSON.stringify({ type: 'react', messageId, reaction }))
//     setMessages(prev => prev.map(m => (m.id === messageId ? ({ ...m, my_reaction: reaction } as any) : m)))
//     const cur = messageIndexRef.current.get(messageId)
//     if (cur) messageIndexRef.current.set(messageId, { ...cur, my_reaction: reaction } as any)
//   }, [])

//   // NEW: מחיקה רכה של הודעה שלי
//   const deleteMessage = useCallback((messageId: string) => {
//     const ws = socketRef.current
//     if (!ws || ws.readyState !== WebSocket.OPEN) return
//     // שליחה לשרת
//     ws.send(JSON.stringify({ type: 'delete', messageId }))

//     // אופטימיסטי: סימון מיידי כמחוק (השרת ישלח message_updated ויסנכרן)
//     setMessages(prev => prev.map(m => (
//       m.id === messageId ? ({ ...m, deleted: true, message: '' } as any) : m
//     )))
//     const cur = messageIndexRef.current.get(messageId)
//     if (cur) messageIndexRef.current.set(messageId, { ...cur, deleted: true, message: '' } as any)
//   }, [])

//   return useMemo(() => ({
//     isConnected,
//     messages,
//     selectedPlayer,
//     sendMessage,
//     selectPlayer,
//     reactToMessage,
//     deleteMessage,          // NEW
//     activePlayers,
//     currentPlayerId,
//     unreadCounts,
//     markRead,
//   }), [
//     isConnected, messages, selectedPlayer, sendMessage, selectPlayer, reactToMessage,
//     deleteMessage, activePlayers, currentPlayerId, unreadCounts, markRead
//   ])
// }

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { Message as ChatMessage, Player, WebSocketMessage, Reaction } from '../types'
import { authStorage } from '../utils/auth'

function backendHost(): string {
  const h = window.location.hostname
  return (h === 'localhost' || h === '127.0.0.1') ? '127.0.0.1' : h
}
function wsUrl(): string {
  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${proto}//${backendHost()}:8000/ws`///??
}
function apiBase(): string {
  const http = window.location.protocol === 'https:' ? 'https:' : 'http:'
  return `${http}//${backendHost()}:8000`
}

type UseWS = {
  isConnected: boolean
  messages: ChatMessage[]
  selectedPlayer: Player | null
  selectPlayer: (p: Player) => void
  sendMessage: (text: string, quotedMessage?: ChatMessage, extras?: { chunkId?: string | null }) => void
  reactToMessage: (id: string, reaction: Reaction) => void
  deleteMessage: (messageId: string) => void
  activePlayers: Player[]
  currentPlayerId?: string
  unreadCounts: Record<string, number>
  markRead: (playerId: string) => void
}

export function useWebSocket(): UseWS {
  const socketRef = useRef<WebSocket | null>(null)

  const [isConnected, setIsConnected] = useState(false)
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [activePlayers, setActivePlayers] = useState<Player[]>([])
  const [selectedPlayer, _setSelectedPlayer] = useState<Player | null>(null)
  const [currentPlayerId, _setCurrentPlayerId] = useState<string>()
  const [unreadCounts, setUnreadCounts] = useState<Record<string, number>>({})

  const selectedPlayerRef = useRef<Player | null>(null)
  const currentPlayerIdRef = useRef<string | undefined>(undefined)
  const seenIdsRef = useRef<Set<string>>(new Set())

  const messageIndexRef = useRef<Map<string, ChatMessage>>(new Map())

  const setSelectedPlayer = useCallback((p: Player | null) => {
    selectedPlayerRef.current = p
    _setSelectedPlayer(p)
  }, [])
  const setCurrentPlayerId = useCallback((id?: string) => {
    currentPlayerIdRef.current = id
    _setCurrentPlayerId(id)
  }, [])

  const attachQuoteIfAny = useCallback((raw: any): ChatMessage => {
    if (raw?.quoted_message && typeof raw.quoted_message === 'object') {
      return raw as ChatMessage
    }
    const quotedId = raw?.quotedId || raw?.quoted_id
    if (quotedId) {
      const q = messageIndexRef.current.get(quotedId)
      if (q) return { ...(raw as ChatMessage), quoted_message: q } as any
    }
    return raw as ChatMessage
  }, [])

  const upsertMessages = useCallback((list: ChatMessage[]) => {
    const withQuotes = list.map(attachQuoteIfAny)
    setMessages(prev => {
      const next = [...prev]
      for (const m of withQuotes) {
        if (!seenIdsRef.current.has(m.id)) {
          next.push(m)
          seenIdsRef.current.add(m.id)
        } else {
          const i = next.findIndex(x => x.id === m.id)
          if (i >= 0) next[i] = { ...next[i], ...m }
        }
      }
      return next
    })
    for (const m of withQuotes) {
      messageIndexRef.current.set(m.id, m)
    }
  }, [attachQuoteIfAny])

  useEffect(() => {
    const url = wsUrl()
    const ws = new WebSocket(url)
    socketRef.current = ws
    console.log('[WS] connecting to', url)

    ws.onopen = () => {
      setIsConnected(true)
      console.log('[WS] open')
      const user = authStorage.getUser()
      if(user?.id){
        ws.send(JSON.stringify({player_id: user.id}))
        setCurrentPlayerId(user.id)
        console.log('[WS] Sent player_id', user.id)
      }
    }
    ws.onerror = (e) => console.error('[WS] error', e)
    ws.onclose = (ev) => {
      console.warn('[WS] close', ev.code, ev.reason)
      setIsConnected(false)
      socketRef.current = null
    }

    ws.onmessage = (ev) => {
      const data: WebSocketMessage | any = JSON.parse(ev.data)
      const me = currentPlayerIdRef.current ?? localStorage.getItem("chat_target_id")//??
      if (data.type === 'history') {
        const sel = selectedPlayerRef.current?.id ?? ''
        const msgs: ChatMessage[] = (data.messages ?? []).map((m: any) => {
          const ts = m.timestamp ?? new Date().toISOString()
          const id = m.id ?? `${ts}|${m.from}|${m.message ?? ''}`
          const base: any = {
            id,
            from: m.from,
            to: m.to ?? (m.from === me ? sel : me),
            message: m.message ?? '',
            timestamp: ts,
            type: m.type === 'bot' ? 'bot' : 'user',
            ...(Array.isArray(m.read_by) ? { read_by: m.read_by } : {}),
            ...(m.my_reaction !== undefined ? { my_reaction: m.my_reaction } : {}),
            ...(m.quoted_message ? { quoted_message: m.quoted_message } : {}),
            ...(m.quotedId ? { quotedId: m.quotedId } : {}),
            ...(m.deleted ? { deleted: true } : {}),          // NEW
            ...(m.updated_at ? { updated_at: m.updated_at } : {}), // NEW
          }
          return attachQuoteIfAny(base)
        })
        seenIdsRef.current = new Set(msgs.map(m => m.id))
        setMessages(msgs)
        for (const m of msgs) messageIndexRef.current.set(m.id, m)
        return
      }

      if (data.type === 'message') {
        const ts: string = data.timestamp ?? new Date().toISOString()
        const sender: string = data.sender ?? 'unknown'
        const id = data.id ?? `${ts}|${sender}|${data.message ?? ''}`
        if (seenIdsRef.current.has(id)) return

        const me = currentPlayerIdRef.current ?? ''
        const sel = selectedPlayerRef.current?.id ?? ''
        const toComputed = (data as any).to ?? (sender === me ? sel : me)

        const raw: any = {
          id,
          from: sender,
          to: toComputed,
          message: data.message ?? '',
          timestamp: ts,
          type: (data as any).isBot ? 'bot' : 'user',
          ...(data.quoted_message ? { quoted_message: data.quoted_message } : {}),
          ...(data.quotedId ? { quotedId: data.quotedId } : {}),
          ...(data.deleted ? { deleted: true } : {}),                 // NEW
          ...(data.updated_at ? { updated_at: data.updated_at } : {}),// NEW
        }

        const msg = attachQuoteIfAny(raw)
        upsertMessages([msg])

        if (toComputed === me && (!selectedPlayerRef.current || selectedPlayerRef.current.id !== sender)) {
          setUnreadCounts(prev => ({ ...prev, [sender]: (prev[sender] || 0) + 1 }))
        }
        return
      }

      if (data.type === 'react') {
        const { messageId, my_reaction } = data as { messageId: string; my_reaction: Reaction }
        setMessages(prev => prev.map(m => (m.id === messageId ? ({ ...m, my_reaction } as any) : m)))
        const cur = messageIndexRef.current.get(messageId)
        if (cur) messageIndexRef.current.set(messageId, { ...cur, my_reaction } as any)
        return
      }

      if (data.type === 'unread') {
        const me = currentPlayerIdRef.current
        if (me && (data as any).to === me) {
          setUnreadCounts(prev => ({ ...prev, [(data as any).from]: (data as any).count }))
        }
        return
      }

      if (data.type === 'message_updated') {
        const u = (data as any).message || (data as any).updated_message
        if (!u?.id) return
        setMessages(prev => prev.map(m => (
          m.id === u.id
            ? ({
                ...m,
                deleted: u.deleted ?? true,
                message: typeof u.text === 'string' ? u.text : '',
                updated_at: u.updated_at ?? m.updated_at,
              } as any)
            : m
        )))
        const cur = messageIndexRef.current.get(u.id)
        if (cur) {
          messageIndexRef.current.set(u.id, {
            ...cur,
            deleted: u.deleted ?? true,
            message: typeof u.text === 'string' ? u.text : '',
            updated_at: u.updated_at ?? cur.updated_at,
          } as any)
        }
        return
      }

      if (data.type === 'typing' || data.type === 'sent') return
      console.warn('Unhandled WS message:', data)
    }

    return () => { try { ws.close() } catch {} }
  }, [attachQuoteIfAny, upsertMessages])

  useEffect(() => {
    const token = new URLSearchParams(window.location.search).get('token') ?? ''
    if (!token) return
    fetch(`${apiBase()}/whoami?token=${encodeURIComponent(token)}`)//??
      .then(r => r.json())
      .then(d => { if (d?.ok) setCurrentPlayerId(d.player_id) })
      .catch(() => {})
  }, [setCurrentPlayerId])

  useEffect(() => {
    const token = new URLSearchParams(window.location.search).get('token') ?? ''
    if (!token) return
    let stop = false
    async function initUnread() {
      try {
        const res = await fetch(`${apiBase()}/unread-summary?token=${encodeURIComponent(token)}`)
        const data = await res.json()
        if (!stop && data?.ok) setUnreadCounts(data.counts || {})
      } catch {}
    }
    initUnread()
    return () => { stop = true }
  }, [])

  useEffect(() => {
    let stop = false
    const tick = async () => {
      try {
        const res = await fetch(`${apiBase()}/players`)
        const data = await res.json()
        if (!stop) setActivePlayers(data)
      } catch {}
    }
    tick()
    const id = setInterval(tick, 3000)
    return () => { stop = true; clearInterval(id) }
  }, [])

  const selectPlayer = useCallback((p: Player) => {
    setSelectedPlayer(p)
    const ws = socketRef.current
    if (!ws || ws.readyState !== WebSocket.OPEN) return

    ws.send(JSON.stringify({ type: 'select', selectedPlayer: p.id }))
    ws.send(JSON.stringify({ type: 'read', with: p.id }))

    setUnreadCounts(prev => ({ ...prev, [p.id]: 0 }))
  }, [setSelectedPlayer])

  const markRead = useCallback((playerId: string) => {
    const ws = socketRef.current
    if (!ws || ws.readyState !== WebSocket.OPEN) return
    ws.send(JSON.stringify({ type: 'read', with: playerId }))
    setUnreadCounts(prev => ({ ...prev, [playerId]: 0 }))
  }, [])

  const sendMessage = useCallback((
    text: string,
    quotedMessage?: ChatMessage,
    extras?: { chunkId?: string | null }
  ) => {
    const ws = socketRef.current
    const sel = selectedPlayerRef.current
    const me = currentPlayerIdRef.current
    if (!ws || ws.readyState !== WebSocket.OPEN) return
    if (!sel || !me) return
    if (!text.trim()) return

    const ts = new Date().toISOString()
    const id = `${ts}|${me}|${text}`

    const payload: any = {
      type: 'message',
      message: text,
      selectedPlayer: sel.id,
      timestamp: ts,
      ...(quotedMessage ? { quotedId: quotedMessage.id } : {}),
    }

    if (extras?.chunkId) {
      payload.chunkId = extras.chunkId
    }

    ws.send(JSON.stringify(payload))

    const optimistic: ChatMessage = {
      id,
      from: me,
      to: sel.id,
      message: text,
      timestamp: ts,
      type: 'user',
      ...(quotedMessage ? { quoted_message: quotedMessage } : {}),
    } as any
    seenIdsRef.current.add(id)
    messageIndexRef.current.set(id, optimistic)
    setMessages(prev => [...prev, optimistic])
  }, [])

  const reactToMessage = useCallback((messageId: string, reaction: Reaction) => {
    const ws = socketRef.current
    if (!ws || ws.readyState !== WebSocket.OPEN) return

    const me = currentPlayerIdRef.current
    const target = messageIndexRef.current.get(messageId)
    if (target && target.from === me) return

    ws.send(JSON.stringify({ type: 'react', messageId, reaction }))
    setMessages(prev => prev.map(m => (m.id === messageId ? ({ ...m, my_reaction: reaction } as any) : m)))
    const cur = messageIndexRef.current.get(messageId)
    if (cur) messageIndexRef.current.set(messageId, { ...cur, my_reaction: reaction } as any)
  }, [])

  const deleteMessage = useCallback((messageId: string) => {
    const ws = socketRef.current
    if (!ws || ws.readyState !== WebSocket.OPEN) return
    ws.send(JSON.stringify({ type: 'delete', messageId }))

    setMessages(prev => prev.map(m => (
      m.id === messageId ? ({ ...m, deleted: true, message: '' } as any) : m
    )))
    const cur = messageIndexRef.current.get(messageId)
    if (cur) messageIndexRef.current.set(messageId, { ...cur, deleted: true, message: '' } as any)
  }, [])

  return useMemo(() => ({
    isConnected,
    messages,
    selectedPlayer,
    sendMessage,
    selectPlayer,
    reactToMessage,
    deleteMessage,          
    activePlayers,
    currentPlayerId,
    unreadCounts,
    markRead,
  }), [
    isConnected, messages, selectedPlayer, sendMessage, selectPlayer, reactToMessage,
    deleteMessage, activePlayers, currentPlayerId, unreadCounts, markRead
  ])
}

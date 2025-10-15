import 'dotenv/config';
import express from 'express';
import http from 'http';
import cors from 'cors';
import jwt from 'jsonwebtoken';
import { createProxyMiddleware } from 'http-proxy-middleware';
import { URL } from 'url';

const PORT = Number(process.env.PORT || 8080);
const JWT_SECRET = process.env.AUTH_JWT_SECRET || 'CHANGE_ME_123456789';
const AUTH_SERVICE_URL = process.env.AUTH_SERVICE_URL || 'http://127.0.0.1:7001';
const GAME_SERVICE_URL = process.env.GAME_SERVICE_URL || 'http://127.0.0.1:7002';
const FRONTEND_ORIGIN = process.env.FRONTEND_ORIGIN || 'http://localhost:5173';

const app = express();

app.use(cors({
  origin: '*',
  credentials: true,
  methods: ['GET','POST','OPTIONS','PUT','DELETE'],
  allowedHeaders: ['Content-Type','Authorization']
}));

// Extract token from headers, query or URL
function getTokenFromReq(req) {
  console.log("in getTokenFromReq function");
  try {
    const hdr = (req.headers && (req.headers.authorization || req.headers.Authorization)) || '';
    if (typeof hdr === 'string' && hdr.startsWith('Bearer ')) return hdr.slice(7);

    if (req.query && typeof req.query.token === 'string') return req.query.token;

    if (req.url) {
      const full = req.url.startsWith('http') ? req.url : `http://localhost${req.url}`;
      const u = new URL(full);
      const q = u.searchParams.get('token');
      if (q) return q;
    }
  } catch {}
  console.log("missing token")
  return null;
}

// Middleware to require JWT for HTTP requests
function requireJWT(req, res, next) {

  console.log("in requireJWT function"); 
  try {
    if (req.method === 'OPTIONS') return res.sendStatus(200);

    const upgrade = (req.headers && req.headers.upgrade) || '';
    if (typeof upgrade === 'string' && upgrade.toLowerCase() === 'websocket') return next();

    const token = getTokenFromReq(req);
    if (!token) return res.status(401).json({ ok: false, error: 'missing_token' });

    req.user = jwt.verify(token, JWT_SECRET);
    next();
  } catch (err) {
    return res.status(401).json({ ok: false, error: 'invalid_token', msg: err.message });
  }
}

// Common proxy options
const commonProxyOptions = {
  changeOrigin: true,
  ws: true,
  logLevel: 'debug',
  onError: (err, req, res) => {
    console.error('[edge][proxy error]', err?.message);
    if (res && !res.headersSent) {
      res.writeHead && res.writeHead(502);
      res.end('Bad gateway');
    }
  }
};

// Auth proxy
const authProxy = createProxyMiddleware({
  target: AUTH_SERVICE_URL,
  pathRewrite: { '^/auth': '' },
  changeOrigin: true,
  ws: true,
  logLevel: 'debug',
  onProxyReq: (proxyReq, req, res) => {
    if (req.body && Object.keys(req.body).length) {
      const bodyData = JSON.stringify(req.body);
      proxyReq.setHeader('Content-Type', 'application/json');
      proxyReq.setHeader('Content-Length', Buffer.byteLength(bodyData));
      proxyReq.write(bodyData);
      proxyReq.end();
    }
  }
});

app.use('/auth', authProxy);



const gameProxy = createProxyMiddleware({
  target: GAME_SERVICE_URL,
  pathRewrite: { '^/game': '/' }, // עוד הגנה - גם אם on upgrade כבר עשינו rewrite
  changeOrigin: true,
  ws: true,
  logLevel: 'debug',
  onProxyReqWs: (proxyReq, req, socket, options, head) => {
    // שלוף token מה־query או מהמקומות האחרים
    try {
      const token = getTokenFromReq(req); // הפונקציה שלך הקיימת
      console.log('[EDGE][WS] onProxyReqWs token preview=', token ? token.slice(0,60) + (token.length>60 ? '...' : '') : '(none)');
      if (token) {
        proxyReq.setHeader('Authorization', `Bearer ${token}`);
      }
      // וודא host מתאים לשירות היעד (מומלץ)
      if (proxyReq.getHeader('host')) {
        proxyReq.setHeader('host', new URL(GAME_SERVICE_URL).host);
      }
    } catch (e) {
      console.error('[EDGE][WS] onProxyReqWs error', e);
    }
  },
});

app.use('/game', (req, res, next) => {
  const upgrade = (req.headers && req.headers.upgrade) || '';
  if (typeof upgrade === 'string' && upgrade.toLowerCase() === 'websocket') return next();
  requireJWT(req, res, next);
}, gameProxy);

// Health endpoint
app.get('/health', (_req, res) => res.json({ ok: true, service: 'edge' }));

// Fallback 404
app.use((_req, res) => {
  console.log('[EDGE] fallback 404', _req.method, _req.url);
  res.status(404).json({ ok: false, error: 'not_found' });
});

// HTTP server with manual upgrade handling
const server = http.createServer(app);

// upgrade handler משודרג — העתק את זה במלואו לתוך edge-server.js
server.on('upgrade', (req, socket, head) => {
  try {
    console.log('--- upgrade event ---');
    console.log('[edge] req.url=', req.url);
    console.log('[edge] remoteAddress=', socket.remoteAddress, 'remotePort=', socket.remotePort);
    console.log('[edge] headers.origin=', req.headers.origin);
    console.log('[edge] headers.upgrade=', req.headers.upgrade);
    console.log('[edge] headers.sec-websocket-key=', req.headers['sec-websocket-key']);
    console.log('[edge] typeof gameProxy.upgrade=', typeof (gameProxy && gameProxy.upgrade));

    // parse token לצורך debug
    try {
      const u = new URL(req.url, `http://${req.headers.host}`);
      const token = u.searchParams.get('token') || '(none)';
      console.log('[edge] token preview=', token ? (token.slice(0,60) + (token.length>60 ? '...' : '')) : '(none)');
    } catch (e) {
      console.log('[edge] failed to parse token', e && e.message);
    }

    if (req.url && req.url.startsWith('/game')) {
      if (typeof gameProxy.upgrade === 'function') {
        // חשוב: rewrite ה-url כדי שה-proxy ישלח ל-target את הנתיב הנכון (/ws ולא /game/ws)
        // נמחק את ה-prefix '/game' לפני שנעביר את ה-request ל-proxy
        req.url = req.url.replace(/^\/game/, '') || '/';
        console.log('[edge] rewritten req.url ->', req.url);

        // לפני העברה: ודא שה־Authorization יעבור ל־target בשלב ה-upgrade
        // (onProxyReqWs גם יכול לטפל בזה, אבל כאן וודאות נוספת)
        // שים לב: אין לנו proxyReq כאן — כך שנשתמש ב-onProxyReqWs להוסיף header ל-proxyReq עצמו.
        try {
          // @ts-ignore - קריאה ל-proxy upgrade
          gameProxy.upgrade(req, socket, head);
          console.log('[edge] gameProxy.upgrade returned (no throw)');
        } catch (err) {
          console.error('[edge][upgrade][error] proxy threw:', err && (err.stack || err.message || err));
          try {
            socket.write('HTTP/1.1 502 Bad Gateway\r\nContent-Type: application/json\r\n\r\n');
            socket.end(JSON.stringify({ ok: false, error: 'ws_upgrade_failed', msg: String(err && err.message) }));
          } catch (writeErr) {
            console.error('[edge] failed to write error to socket:', writeErr && writeErr.message);
          }
        }
        return;
      } else {
        console.warn('[edge] gameProxy.upgrade not available -> destroying socket');
        socket.destroy();
        return;
      }
    }

    // לא /game — סוגר
    socket.destroy();
  } catch (err) {
    console.error('[edge][upgrade] outer error:', err && (err.stack || err.message || err));
    try { socket.destroy(); } catch (_) {}
  }
});


server.listen(PORT, () => {
  console.log(`[edge] listening on http://localhost:${PORT}`);
  console.log(`[edge] auth → ${AUTH_SERVICE_URL}`);
  console.log(`[edge] game → ${GAME_SERVICE_URL}`);
});
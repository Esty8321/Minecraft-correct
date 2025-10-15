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
const FRONTEND_ORIGIN = process.env.CORS_ORIGIN || 'http://localhost:5173';

const app = express();

// --------------------- CORS ---------------------
app.use(cors({
  origin: FRONTEND_ORIGIN,
  credentials: true,
  methods: ['GET', 'POST', 'OPTIONS', 'PUT', 'DELETE'],
  allowedHeaders: ['Content-Type', 'Authorization']
}));

// handle preflight requests
app.options('*', cors({
  origin: FRONTEND_ORIGIN,
  credentials: true,
  methods: ['GET', 'POST', 'OPTIONS', 'PUT', 'DELETE'],
  allowedHeaders: ['Content-Type', 'Authorization']
}));

// --------------------- Logging ---------------------
app.use((req, res, next) => {
  console.log('[EDGE][INCOMING]', req.method, req.url, 'origin=', req.headers.origin, 'host=', req.headers.host);
  next();
});

// --------------------- JSON parser ---------------------
// app.use(express.json());

// --------------------- Token helpers ---------------------
function getTokenFromReq(req) {
  try {
    const hdr = (req.headers && (req.headers.authorization || req.headers.Authorization)) || '';
    if (typeof hdr === 'string' && hdr.startsWith('Bearer ')) {
      return hdr.slice(7);
    }
    if (req.query && typeof req.query.token === 'string') return req.query.token;
    if (req.url) {
      const full = req.url.startsWith('http') ? req.url : `http://localhost${req.url}`;
      const u = new URL(full);
      console.log("u--   ",u);
      
      return u.searchParams.get('token') || null;
    }
  } catch {console.log("an error in get token--");
   }
  return null;
}

function requireJWT(req, res, next) {
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

// --------------------- /auth proxy ---------------------
const authProxy = createProxyMiddleware({
  target: AUTH_SERVICE_URL,
  pathRewrite: { '^/auth': '' },
  changeOrigin: true,
  ws: false,
  logLevel: 'debug',
  onProxyReq: (proxyReq, req, res) => {
    console.log("--I am here")
    if (req.body && Object.keys(req.body).length) {
      const bodyData = JSON.stringify(req.body);
      proxyReq.setHeader('Content-Type', 'application/json');
      proxyReq.setHeader('Content-Length', Buffer.byteLength(bodyData));
      proxyReq.write(bodyData);
      proxyReq.end();
    }
  },
  onError: (err, req, res) => {
    console.error('[EDGE][auth proxy error]', err?.message);
    if (res && !res.headersSent) {
      res.writeHead && res.writeHead(502);
      res.end('Bad gateway');
    }
  }
});

app.use('/auth', authProxy);

// --------------------- /game proxy ---------------------
const gameProxy = createProxyMiddleware({
  target: GAME_SERVICE_URL,
  pathRewrite: { '^/game': '/' },
  changeOrigin: true,
  ws: true,
  logLevel: 'debug',
  onProxyReqWs: (proxyReq, req, socket, options, head) => {
    try {
      const token = getTokenFromReq(req);
      if (token) proxyReq.setHeader('Authorization', `Bearer ${token}`);
      if (proxyReq.getHeader('host')) {
        proxyReq.setHeader('host', new URL(GAME_SERVICE_URL).host);
      }
    } catch (e) {
      console.error('[EDGE][WS] onProxyReqWs error', e);
    }
  }
});

// HTTP requests to /game require JWT
app.use('/game', (req, res, next) => {
  const upgrade = (req.headers && req.headers.upgrade) || '';
  if (typeof upgrade === 'string' && upgrade.toLowerCase() === 'websocket') return next();
  requireJWT(req, res, next);
}, gameProxy);

// --------------------- health check ---------------------
app.get('/health', (_req, res) => res.json({ ok: true, service: 'edge' }));

// --------------------- fallback ---------------------
app.use((_req, res) => {
  res.status(404).json({ ok: false, error: 'not_found' });
});

// --------------------- HTTP server + WS upgrade ---------------------
const server = http.createServer(app);

server.on('upgrade', (req, socket, head) => {
  try {
    if (req.url && req.url.startsWith('/game')) {
      req.url = req.url.replace(/^\/game/, '') || '/';
      try {
        const token = getTokenFromReq(req);
        // Authorization added automatically in onProxyReqWs
      } catch { }
      if (typeof gameProxy.upgrade === 'function') {
        return gameProxy.upgrade(req, socket, head);
      }
      socket.destroy();
      return;
    }
    socket.destroy();
  } catch {
    try { socket.destroy(); } catch { }
  }
});

server.listen(PORT, () => {
  console.log(`[edge] listening on http://localhost:${PORT}`);
  console.log(`[edge] auth → ${AUTH_SERVICE_URL}`);
  console.log(`[edge] game → ${GAME_SERVICE_URL}`);
});




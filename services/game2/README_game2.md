# game2 — Voxel Game Server & Bot (Microservices)

> **TL;DR**: This folder provides a FastAPI WebSocket server for a voxel board game, split into clear microservices (**world**, **movement**, **messaging**, **sessions**, **manager**).
> A lightweight **GRU-based bot** keeps a player moving when they disconnect. Training uses your action-history logs. 🧠🎮

---

## Overview

- **Realtime board**: a `64×64` grid per *chunk*. Each cell encodes flags and color bits in a single `uint8` value.
- **WebSocket gameplay**: clients send simple commands (move, color++, message); server broadcasts updated chunks.
- **Persistence**: world/players/messages/history are stored under `data/`.
- **Autopilot bot**: when a player disconnects, a GRU policy can take over and continue basic actions in their name.
- **JWT auth**: connections must include a valid token (`sub` or `id` = user id).

---

## Folder Structure

```
services/game2/
├─ api/
│  └─ main.py              # FastAPI app & WebSocket endpoint (/ws)
├─ core/
│  ├─ bits.py              # Bit-level helpers (player flag, color bits, link flag)
│  ├─ ids.py               # Chunk id helpers
│  └─ settings.py          # Global constants & data paths
├─ data/
│  ├─ db_chunks.py         # Load/save chunk boards
│  ├─ db_players.py        # Persist player positions
│  ├─ db_messages.py       # Persist cell-linked messages (“treasures”)
│  └─ db_history.py        # Append action history (+ JSONL log for training)
├─ hub/
│  ├─ manager.py           # The Hub: wires all services & lifecycle (connect/disconnect)
│  ├─ world.py             # WorldService: chunk cache, spawn/despawn, compose entry cells
│  ├─ movement.py          # MovementService: in-chunk move + cross-chunk transfer
│  ├─ messaging.py         # MessagingService: write/send messages, broadcast chunk, notices
│  ├─ sessions.py          # SessionStore: sockets ↔ users, watchers per chunk
│  ├─ helper.py            # utilities: auth (JWT), coords math, WS fanout, bounds etc.
│  ├─ types.py             # Typed payloads, dataclasses (PlayerState, Coord), enums
│  └─ bot.py               # BotService: load GRU, tick loop, perform actions
├─ models/
│  ├─ bot_gru.py           # CNN+GRU single-step policy (board + prev action + user emb → logits)
│  └─ bot_gru_v2.py        # (alt/iteration) second version
└─ train/
   └─ train_bot.py         # Reads JSONL history → trains policy → saves bot_gru.pt
```

> In your upload, the package path is `services.game2...`. Make sure your project root exposes a `services/` package containing this `game2/` folder.

---

## Data & Encoding

- **Board tensor**: `torch.uint8` matrix (`H=W=64` by default).
- **Bits** (`core/settings.py`):
  - `BIT_IS_PLAYER = 0`
  - `BIT_HAS_LINK  = 1` → mark a cell with an attached message/“treasure”
  - `BIT_R0..B1`   → two bits per channel for a tiny RGB palette
- **Files** (relative to repo root):
  - `data/world.db`        — chunk storage
  - `data/players.db`      — last known player positions
  - `data/message.json`    — per-cell message store
  - `data/history.json`    — compact per-player index
  - `data/history.jsonl`   — *line* log; each row contains `{player_id, chunk_id, token, board, ts}`

---

## Runtime Flow (Services)

### 1) Connection & Routing — `hub/manager.py`
- Accepts a WebSocket, verifies token (`helper.verify_token_or_reason`).
- Restores prior position if found (`data/db_players.get_player_position`), else picks a random empty spawn in the root chunk.
- Wires the socket into **SessionStore** and attaches it as a watcher of the current chunk.
- On **disconnect**: if it’s the **last** socket for that user, the **BotService** is started with the last `PlayerState`.

### 2) World — `hub/world.py`
- Maintains a cache of chunk boards in memory and per-chunk locks.
- `ensure_chunk(chunk_id)` lazily loads or initializes a board.
- `spawn_player`/`despawn_player` updates the board and persists both the board and player position.

### 3) Movement — `hub/movement.py`
- Validates bounds and emptiness, updates board using `world.compose_entry_cells`.
- Supports **cross-chunk transfers** when stepping off the edge: computes target chunk via `neighbor_chunk_id` + `edge_target_for_direction` and moves the player atomically between chunk locks.
- Persists the new board and position; lets **MessagingService** broadcast changes.

### 4) Messaging — `hub/messaging.py`
- `write_message` stores a message at the player’s current cell, flips `BIT_HAS_LINK`, saves chunk, broadcasts, and emits an **announcement**: _“A player hid a treasure”_.
- `maybe_send_message_at` checks when a player stands on a link-cell and delivers the linked message (once).
- Also records player actions in history (`db_history.append_player_action`).

### 5) Sessions — `hub/sessions.py`
- Tracks: sockets per user, a single `PlayerSession` per socket, and sets of watchers per chunk.
- Used by `MessagingService.broadcast_chunk` to fan out the latest board to all watchers.

### 6) Bot — `hub/bot.py`
- Lazy-loads weights (`bot_gru.pt`) and a `user_vocab` mapping.
- Every **T=0.30s**: runs `GRUPolicy.forward_step(board, last_token, user_idx, h)`; chooses the next action; executes via **MovementService** or color++.
- If the bot crosses into a new chunk, it forces a broadcast of the new chunk’s board.
- Stops when the real player reconnects (or `Hub.stop` is called).

---

## WebSocket API

**URL**: `ws://<host>:<port>/ws?token=<JWT>`

- **Auth**: JWT is required. The server decodes using:
  - `AUTH_JWT_SECRET` (default `"CHANGE_ME_123456789"`)
  - `JWT_ALG` (default `"HS256"`)
  - Uses `sub` or `id` from the token as `user_id`.

**Client → Server** (JSON):
```jsonc
// Movement
{ "k": "up" }       // also: "down" | "left" | "right"

// Color++
{ "k": "c" }        // also: "color" | "color++"

// Write a message (“treasure”)
{ "k": "m", "content": "Hello from cell!" }

// Where am I (utility)
{ "k": "whereami" }
```

**Server → Client**:
- `{ "type": "matrix", "w": 64, "h": 64, "data": [...], "chunk_id": "...", "total_players": N }` — full board for the watched chunk.
- `{ "type": "message", "data": { "content": "...", "author": "...", ... } }` — cell-linked message at current position.
- `{ "type": "announcement", "data": { "text": "A player hid a treasure" } }` — broadcast after someone writes a message.

**REST helper**:
- `GET /nearest-player/{player_id}` → `{ ok, nearest }` (by chunk proximity).

---

## How the Model Integrates

1. **Data Collection**: Every player move (and color++) is appended to `data/history.json` and a structured row is written to `data/history.jsonl`.
2. **Training** (`train/train_bot.py`):
   - Reads `history.jsonl`, sorts by timestamp per `(player_id, chunk_id)` session.
   - Builds a **user vocabulary**.
   - For each step, creates a sample `(board_t, prev_action_t, user_idx) → next_action_{t+1}`.
   - Trains `models/bot_gru.py` (CNN to embed board, concat with previous action bits + user embedding, then **GRU → logits**) to predict the next of 6 actions.
   - Saves weights to `bot_gru.pt` with the vocab.
3. **Runtime** (`hub/bot.py`):
   - On last-socket disconnect, `Hub` calls `BotService.start(user_id, last_state)`.
   - Bot loads `bot_gru.pt` (if not loaded), enters a loop, and calls Movement/World services to act & broadcast.

---

## Running the Server

### 1) Install dependencies
pip install -r requirements.txt


### 2) Set environment (JWT)
```bash
# macOS/Linux
export AUTH_JWT_SECRET="CHANGE_ME_123456789"
export JWT_ALG="HS256"

# Windows PowerShell
$env:AUTH_JWT_SECRET = "CHANGE_ME_123456789"
$env:JWT_ALG = "HS256"
```

### 3) Ensure PYTHONPATH and run
The code imports as `services.game2...`. From repo root (where `services/` lives):

```bash
# macOS/Linux
export PYTHONPATH=.
uvicorn services.game2.api.main:app --reload --port 8000

# Windows PowerShell
$env:PYTHONPATH = "."
uvicorn services.game2.api.main:app --reload --port 8000
```

- WebSocket endpoint: `ws://localhost:8000/ws?token=<JWT>`
- Example JWT payload should include `sub` or `id` with the user id.

---

## Training the Bot

1. **Collect Data**: Run the game, play a while to generate `data/history.jsonl` (it is appended during movement/color events).
2. **Train**:
```bash
# From repo root (services/ on PYTHONPATH)
python -m services.game2.train.train_bot  # saves weights to bot_gru.pt
```
3. **Place Weights**: Ensure `bot_gru.pt` is available in the working directory that runs the server, or update `BotService.load_model(weights_path)`.

> Tip: if CUDA is available, you can adapt the training script to move tensors to GPU.

---

## Useful Notes

- **Chunk broadcasts**: after every movement or write, the server broadcasts the full chunk matrix to all its watchers.
- **Cross-chunk travel**: stepping off an edge moves you to the opposite edge of the adjacent chunk, with correct bit-carry and atomic persistence.
- **Messages as “treasures”**: writing a message at your cell flips `BIT_HAS_LINK` so clients can detect and fetch it.
- **Bot safety**: the bot is intentionally simple; it can be disabled or replaced. It only acts for users without any live sockets attached.
- **Extending actions**: add tokens to `data/db_history.py::ActionToken` and wire handling in `hub/bot.py` and the API.

---

## Quick Smoke Test

1. Start the server (see _Running the Server_).
2. Connect two browser tabs/clients with **different JWTs**.
3. Move around with `{ "k": "up" | "down" | "left" | "right" }`.
4. Send a message: `{ "k": "m", "content": "secret 💎" }` and observe the announcement + link bit.
5. Close a tab; watch the bot take over for that user (chunk broadcasts continue).

---

## License & Credits

Internal bootcamp project. © You & team.
Model pieces inspired by classic CNN+GRU pipelines for action prediction.
